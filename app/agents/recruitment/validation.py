"""Recruitment Validation Agent: gate write actions and set route."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_short_term
from app.models.decision import EXECUTABLE_OUTCOMES, HUMAN_APPROVAL_OUTCOMES
from app.orchestration.state import WorkflowState
from app.tools.catalog import get_registry

VALID_OUTCOMES = {"approve", "reject", "pending_approval", "escalate", "recommend"}


def recruitment_validation_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    policy_results = state.get("policy_results") or {}
    analysis = state.get("analysis_results") or {}
    issues: list[str] = []

    _, notes_patch = search_short_term(state, agent="recruitment_validation")

    outcome = decision.get("outcome")
    if outcome not in VALID_OUTCOMES:
        issues.append("Decision outcome is missing or invalid.")
    if not decision.get("rationale"):
        issues.append("Decision is missing a rationale.")

    shortlist = list(analysis.get("shortlist_candidates") or [])
    if outcome == "approve":
        if not shortlist:
            issues.append("Approve/shortlist decision has no shortlist candidates.")
        if not policy_results.get("eligible", False):
            issues.append("Approve decision conflicts with policy eligibility.")
        if not decision.get("executable"):
            issues.append("Approve decision is not marked executable.")
        write_names = {tool.spec.name for tool in get_registry().find_write_tools()}
        pending = state.get("pending_actions") or []
        if not pending:
            issues.append("Approve decision has no pending write actions.")
        for action in pending:
            action_type = action.get("type")
            if action_type not in write_names:
                issues.append(f"Pending action '{action_type}' is not a registered write tool.")

    if outcome == "pending_approval" and not shortlist:
        issues.append("Pending approval requires at least one shortlist candidate.")

    if outcome in HUMAN_APPROVAL_OUTCOMES and not state.get("requires_human_approval"):
        issues.append("Human-approval decision is missing the human-approval flag.")

    if outcome in {"reject", "recommend"} and decision.get("executable"):
        issues.append(f"{outcome} decisions must not be executable.")

    # Never allow shortlist writes when policy blockers remain for those candidates.
    validations = {
        str(item.get("candidate_id")): item
        for item in policy_results.get("candidate_validations") or []
    }
    for candidate_id in shortlist:
        item = validations.get(candidate_id) or {}
        if item.get("violations"):
            issues.append(
                f"Shortlist candidate {candidate_id} still has policy violations."
            )
        if not item.get("eligible_for_shortlist"):
            issues.append(
                f"Shortlist candidate {candidate_id} is not policy-eligible."
            )

    passed = len(issues) == 0
    if not passed:
        route = "response"
        status = "validation_failed"
    elif state.get("requires_human_approval") or outcome in HUMAN_APPROVAL_OUTCOMES:
        route = "response"
        status = "awaiting_human_approval"
    elif outcome in EXECUTABLE_OUTCOMES and decision.get("executable"):
        route = "action"
        status = "validated"
    else:
        route = "response"
        status = "validated"

    metadata = {
        **state.get("metadata", {}),
        "validation": {
            "passed": passed,
            "issues": issues,
            "route": route,
        },
        "route": route,
    }

    return node_update(
        "recruitment_validation",
        f"Validation {'passed' if passed else 'failed'}; route={route}; issues={len(issues)}.",
        status=status,
        errors=[f"Validation: {item}" for item in issues],
        metadata=metadata,
        **combine_patches(notes_patch),
    )

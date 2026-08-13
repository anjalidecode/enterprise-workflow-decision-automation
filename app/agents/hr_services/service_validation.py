"""Service Validation: gate writes, enforce auth/org isolation, set route."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import search_short_term
from app.models.decision import EXECUTABLE_OUTCOMES, HUMAN_APPROVAL_OUTCOMES
from app.orchestration.state import WorkflowState
from app.tools.catalog import get_registry

VALID_OUTCOMES = {
    "approve",
    "reject",
    "pending_approval",
    "escalate",
    "recommend",
    "ready",
    "blocked",
}

HIGH_IMPACT_ACTIONS = {
    "terminate",
    "terminate_employment",
    "change_salary",
    "update_salary",
    "update_payroll",
    "change_employment_status",
    "update_performance_record",
    "demote",
    "reduce_salary",
}


def service_validation_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    policy_results = state.get("policy_results") or {}
    analysis = state.get("analysis_results") or {}
    authorization = (state.get("metadata") or {}).get("authorization") or analysis.get(
        "authorization"
    ) or {}
    issues: list[str] = []

    _, notes_patch = search_short_term(state, agent="service_validation")

    outcome = decision.get("outcome")
    if outcome not in VALID_OUTCOMES:
        issues.append("Decision outcome is missing or invalid.")
    if not decision.get("rationale"):
        issues.append("Decision is missing a rationale.")

    pending = state.get("pending_actions") or []
    write_names = {tool.spec.name for tool in get_registry().find_write_tools()}
    write_names.add("notify_employee")

    for action in pending:
        action_type = str(action.get("type") or "")
        if action_type in HIGH_IMPACT_ACTIONS:
            issues.append(f"High-impact action '{action_type}' is not permitted.")
        if action_type not in {"request_human_approval"} and action_type not in write_names:
            issues.append(f"Pending action '{action_type}' is not a registered write tool.")

    if authorization.get("disclosure_blocked") and outcome in EXECUTABLE_OUTCOMES:
        issues.append("Executable decision blocked by authorization disclosure rules.")

    if outcome == "ready":
        if not decision.get("executable"):
            issues.append("Ready decision is not marked executable.")
        knowledge_only = str(analysis.get("category") or "") in {
            "policy_information",
            "benefits",
            "training",
        }
        if not pending and not knowledge_only:
            issues.append("Ready decision has no pending write actions.")

    if outcome == "blocked":
        if decision.get("executable"):
            issues.append("Blocked decisions must not be executable.")
        if not (
            decision.get("blockers")
            or analysis.get("blockers")
            or policy_results.get("violations")
        ):
            issues.append("Blocked decision is missing blockers.")

    if outcome == "pending_approval":
        if decision.get("executable"):
            issues.append("Pending-approval decisions must not be executable before approval.")

    if outcome in HUMAN_APPROVAL_OUTCOMES and not state.get("requires_human_approval"):
        issues.append("Human-approval decision is missing the human-approval flag.")

    if outcome in {"blocked", "reject", "recommend"} and decision.get("executable"):
        issues.append(f"{outcome} decisions must not be executable.")

    if policy_results.get("severity") == "blocked" and outcome in EXECUTABLE_OUTCOMES:
        issues.append("Executable decision blocked by policy blockers.")

    # Determine branch: resolve / create_ticket / escalate
    route_hint = str(
        (decision.get("entity_refs") or {}).get("route_hint")
        or (state.get("metadata") or {}).get("hr_services_route_hint")
        or policy_results.get("route_hint")
        or "resolve"
    )

    passed = len(issues) == 0
    if not passed:
        route = "escalate"
        branch = "blocked"
        status = "validation_failed"
    elif state.get("requires_human_approval") or outcome in HUMAN_APPROVAL_OUTCOMES:
        route = "escalate"
        branch = "review"
        status = "awaiting_human_approval"
    elif outcome in EXECUTABLE_OUTCOMES and decision.get("executable"):
        if route_hint == "create_ticket" or analysis.get("requires_document") or analysis.get(
            "requires_hr_ticket"
        ) or analysis.get("requires_escalation"):
            route = "create_ticket"
            branch = "create_ticket"
        else:
            route = "resolve"
            branch = "resolve"
        status = "validated"
    else:
        route = "escalate"
        branch = "blocked" if outcome == "blocked" else "response"
        status = "validated"

    metadata = {
        **state.get("metadata", {}),
        "validation": {
            "passed": passed,
            "issues": issues,
            "route": route,
            "branch": branch,
        },
        "route": route,
        "decision_branch": branch,
    }

    return node_update(
        "service_validation",
        (
            f"Validation {'passed' if passed else 'failed'}; "
            f"branch={branch}; route={route}; issues={len(issues)}."
        ),
        status=status,
        errors=[f"Validation: {item}" for item in issues],
        metadata=metadata,
        **combine_patches(notes_patch),
    )

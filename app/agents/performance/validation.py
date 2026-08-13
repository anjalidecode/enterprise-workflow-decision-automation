"""Performance Validation Agent: gate write actions and set route."""

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
    "demote",
    "reduce_salary",
    "disciplinary_action",
    "punish",
}


def performance_validation_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    policy_results = state.get("policy_results") or {}
    analysis = state.get("analysis_results") or {}
    issues: list[str] = []

    _, notes_patch = search_short_term(state, agent="performance_validation")

    outcome = decision.get("outcome")
    if outcome not in VALID_OUTCOMES:
        issues.append("Decision outcome is missing or invalid.")
    if not decision.get("rationale"):
        issues.append("Decision is missing a rationale.")

    severity = policy_results.get("severity")
    pending = state.get("pending_actions") or []
    write_names = {tool.spec.name for tool in get_registry().find_write_tools()}
    write_names.add("notify_employee")

    for action in pending:
        action_type = str(action.get("type") or "")
        if action_type in HIGH_IMPACT_ACTIONS:
            issues.append(f"High-impact action '{action_type}' is not permitted.")
        if action_type not in {"request_human_approval"} and action_type not in write_names:
            issues.append(f"Pending action '{action_type}' is not a registered write tool.")

    if outcome == "ready":
        if severity not in {"development", "concern"}:
            issues.append("Ready/development actions require policy severity=development or concern.")
        if not decision.get("executable"):
            issues.append("Ready decision is not marked executable.")
        if not pending:
            issues.append("Ready decision has no pending write actions.")

    if outcome == "blocked":
        if decision.get("executable"):
            issues.append("Blocked decisions must not be executable.")
        if not (
            decision.get("blockers")
            or analysis.get("blockers")
            or policy_results.get("violations")
            or analysis.get("scan_mode")
        ):
            if analysis.get("employee_id") or (state.get("entities") or {}).get("employee_id"):
                issues.append("Blocked decision is missing blockers.")

    if outcome == "escalate":
        if decision.get("executable"):
            issues.append("Escalate decisions must not be executable before approval.")
        if not policy_results.get("requires_human_approval") and severity != "escalation":
            issues.append("Escalate decision requires escalation severity or approval flag.")

    if outcome in HUMAN_APPROVAL_OUTCOMES and not state.get("requires_human_approval"):
        issues.append("Human-approval decision is missing the human-approval flag.")

    if outcome in {"blocked", "reject", "recommend"} and decision.get("executable"):
        issues.append(f"{outcome} decisions must not be executable.")

    if policy_results.get("severity") == "escalation" and outcome in EXECUTABLE_OUTCOMES:
        issues.append("Executable decision blocked by escalation-level policy severity.")
    if policy_results.get("severity") == "blocked" and outcome in EXECUTABLE_OUTCOMES:
        issues.append("Executable decision blocked by policy blockers.")

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
        "performance_validation",
        f"Validation {'passed' if passed else 'failed'}; route={route}; issues={len(issues)}.",
        status=status,
        errors=[f"Validation: {item}" for item in issues],
        metadata=metadata,
        **combine_patches(notes_patch),
    )

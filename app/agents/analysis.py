"""Analysis Agent: interpret leave impact from tools and recommend an outcome."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def analysis_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    policy_results = state.get("policy_results") or {}
    errors: list[str] = []

    impact_result, impact_patch = invoke_tool(
        state,
        agent="analysis",
        capability="leave.impact",
        payload={
            "employee_id": leave_request.get("employee_id"),
            "days": leave_request.get("days"),
            "leave_type": leave_request.get("leave_type", "annual"),
        },
    )

    blockers: list[str] = list(policy_results.get("violations", []))
    if not impact_result.success:
        errors.append(impact_result.error_message or "Leave impact calculation failed.")
        impact: dict[str, Any] = {}
        blockers.append("Leave impact could not be calculated.")
    else:
        impact = dict(impact_result.data or {})

    available = impact.get("available_days")
    remaining_after = impact.get("remaining_after")
    sufficient_balance = bool(impact.get("sufficient_balance"))
    employment_active = bool(impact.get("employment_active"))
    employee_found = bool(impact.get("employee_found"))

    if employee_found and not sufficient_balance and not any("balance" in item for item in blockers):
        blockers.append("Insufficient leave balance.")
    if employee_found and not employment_active and not any("active" in item.lower() for item in blockers):
        blockers.append("Employee is not active.")
    if not employee_found:
        blockers.append("No employee record available for analysis.")

    if policy_results.get("requires_human_approval"):
        recommendation = "escalate_for_approval" if not blockers else "reject"
    elif blockers:
        recommendation = "reject"
    else:
        recommendation = "approve"

    analysis_results = {
        "employee_id": leave_request.get("employee_id"),
        "requested_days": leave_request.get("days"),
        "available_days": available,
        "remaining_after": remaining_after,
        "sufficient_balance": sufficient_balance,
        "employment_active": employment_active,
        "requires_human_approval": bool(policy_results.get("requires_human_approval")),
        "blockers": blockers,
        "recommendation": recommendation,
    }

    summary = (
        f"Analysis recommendation={recommendation}; "
        f"balance={available}, requested={leave_request.get('days')}, blockers={len(blockers)}."
    )
    return node_update(
        "analysis",
        summary,
        analysis_results=analysis_results,
        errors=errors,
        **impact_patch,
    )

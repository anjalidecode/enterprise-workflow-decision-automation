"""Analysis Agent: compare request, employee data, and policy findings."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState


def analysis_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    employee = state.get("employee_data") or {}
    policy_results = state.get("policy_results") or {}
    days = leave_request.get("days")
    leave_type = leave_request.get("leave_type", "annual")
    available = None
    if employee:
        available = employee.get("leave_balances", {}).get(leave_type)

    blockers: list[str] = list(policy_results.get("violations", []))
    remaining_after = None
    sufficient_balance = False

    if isinstance(days, int) and isinstance(available, int):
        sufficient_balance = days <= available
        remaining_after = available - days
        if not sufficient_balance and not any("balance" in item for item in blockers):
            blockers.append("Insufficient leave balance.")

    employment_active = employee.get("employment_status") == "active" if employee else False
    if employee and not employment_active and not any("active" in item.lower() for item in blockers):
        blockers.append("Employee is not active.")

    if not employee:
        blockers.append("No employee record available for analysis.")

    if policy_results.get("requires_human_approval"):
        recommendation = "escalate_for_approval" if not blockers else "reject"
    elif blockers:
        recommendation = "reject"
    else:
        recommendation = "approve"

    analysis_results = {
        "employee_id": leave_request.get("employee_id"),
        "requested_days": days,
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
        f"balance={available}, requested={days}, blockers={len(blockers)}."
    )
    return node_update("analysis", summary, analysis_results=analysis_results)

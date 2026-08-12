"""Response Agent: produce the final workflow response from shared state."""

from __future__ import annotations

from typing import Any

from app.agents.common import node_update
from app.orchestration.state import WorkflowState


def response_agent(state: WorkflowState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    outcome = decision.get("outcome", "unknown")
    employee = state.get("employee_data") or {}
    leave_request = (state.get("metadata") or {}).get("leave_request") or {}
    validation = (state.get("metadata") or {}).get("validation") or {}
    name = employee.get("name") or leave_request.get("employee_id") or "the employee"
    days = leave_request.get("days")
    start_date = leave_request.get("start_date")

    if not validation.get("passed", True) and validation.get("issues"):
        status = "failed"
        final_response = (
            "Leave workflow could not be completed because validation failed: "
            + "; ".join(validation["issues"])
        )
    elif state.get("requires_human_approval"):
        status = "awaiting_human_approval"
        final_response = (
            f"Leave request for {name} ({days} day(s) from {start_date}) "
            "requires human approval before any leave action is executed. "
            f"Reason: {decision.get('rationale', 'policy threshold reached.')}"
        )
    elif outcome == "approve":
        status = "completed"
        balances = employee.get("leave_balances") or {}
        remaining = balances.get(leave_request.get("leave_type", "annual"))
        final_response = (
            f"Leave approved for {name}: {days} day(s) starting {start_date}. "
            f"Simulated remaining annual balance: {remaining}."
        )
    elif outcome == "reject":
        status = "completed"
        final_response = (
            f"Leave request for {name} was rejected. "
            f"Reason: {decision.get('rationale', 'policy requirements were not met.')}"
        )
    else:
        status = "failed" if state.get("errors") else "completed"
        final_response = decision.get("rationale") or "Workflow finished without an executable decision."

    summary = f"Composed final response; status={status}."
    return node_update(
        "response",
        summary,
        status=status,
        final_response=final_response,
    )

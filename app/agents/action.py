"""Action Agent: execute approved, validated actions against simulated systems."""

from __future__ import annotations

from typing import Any

from app.agents.common import node_update, utc_now
from app.orchestration.state import WorkflowState


def action_agent(state: WorkflowState) -> dict[str, Any]:
    pending = list(state.get("pending_actions") or [])
    employee = dict(state.get("employee_data") or {})
    completed: list[dict[str, Any]] = []

    for action in pending:
        action_type = action.get("type")
        record = {
            **action,
            "status": "simulated",
            "executed_at": utc_now(),
        }
        if action_type == "simulate_leave_balance_update":
            leave_type = action.get("leave_type", "annual")
            days = int(action.get("days") or 0)
            balances = dict(employee.get("leave_balances") or {})
            previous = int(balances.get(leave_type, 0))
            new_balance = previous - days
            balances[leave_type] = new_balance
            employee["leave_balances"] = balances
            record["previous_balance"] = previous
            record["new_balance"] = new_balance
        completed.append(record)

    summary = f"Executed {len(completed)} simulated action(s)."
    return node_update(
        "action",
        summary,
        employee_data=employee,
        completed_actions=completed,
        pending_actions=[],
        status="actions_executed",
    )

"""Research Agent: retrieve employee and leave-balance records via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool, merge_tool_patches


def research_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    employee_id = leave_request.get("employee_id")
    leave_type = leave_request.get("leave_type", "annual")
    errors: list[str] = []
    patches: list[dict[str, Any]] = []

    if not employee_id:
        return node_update(
            "research",
            "No employee id available; skipped enterprise lookup.",
            employee_data={},
            retrieved_data={"source": "simulated_hr_store", "found": False},
            errors=["Research skipped: missing employee id."],
        )

    employee_result, employee_patch = invoke_tool(
        state,
        agent="research",
        capability="employee.lookup",
        payload={"employee_id": employee_id},
    )
    patches.append(employee_patch)

    balance_result, balance_patch = invoke_tool(
        state,
        agent="research",
        capability="employee.leave_balance",
        payload={"employee_id": employee_id, "leave_type": leave_type},
    )
    patches.append(balance_patch)

    if not employee_result.success:
        errors.append(
            employee_result.error_message
            or f"Employee {employee_id} was not found in the HR store."
        )
        retrieved = {
            "source": employee_result.source,
            "found": False,
            "employee_id": employee_id,
            "error_code": employee_result.error_code,
        }
        summary = f"No HR record found for {employee_id}."
        employee_data: dict[str, Any] = {}
    else:
        employee_data = dict(employee_result.data or {})
        balance = (balance_result.data or {}).get("balance") if balance_result.success else None
        if not balance_result.success:
            errors.append(balance_result.error_message or "Leave balance lookup failed.")
        retrieved = {
            "source": employee_result.source,
            "found": True,
            "employee_id": employee_data.get("employee_id"),
            "employment_status": employee_data.get("employment_status"),
            "annual_leave_balance": balance,
            "department": employee_data.get("department"),
            "manager": employee_data.get("manager"),
        }
        summary = (
            f"Retrieved {employee_data.get('name')} ({employee_id}): "
            f"status={employee_data.get('employment_status')}, "
            f"annual_balance={balance}."
        )

    return node_update(
        "research",
        summary,
        employee_data=employee_data,
        retrieved_data=retrieved,
        errors=errors,
        **merge_tool_patches(*patches),
    )

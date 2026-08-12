"""Research Agent: retrieve employee and leave-balance records."""

from __future__ import annotations

from typing import Any

from app.agents.common import leave_request_from_state, node_update
from app.orchestration.state import WorkflowState
from app.services import hr_data


def research_agent(state: WorkflowState) -> dict[str, Any]:
    leave_request = leave_request_from_state(state)
    employee_id = leave_request.get("employee_id")
    errors: list[str] = []

    if not employee_id:
        return node_update(
            "research",
            "No employee id available; skipped enterprise lookup.",
            employee_data={},
            retrieved_data={"source": "simulated_hr_store", "found": False},
            errors=["Research skipped: missing employee id."],
        )

    employee = hr_data.get_employee(str(employee_id))
    if employee is None:
        errors.append(f"Employee {employee_id} was not found in the HR store.")
        retrieved = {
            "source": "simulated_hr_store",
            "found": False,
            "employee_id": employee_id,
        }
        summary = f"No HR record found for {employee_id}."
        employee_data: dict[str, Any] = {}
    else:
        balances = dict(employee.get("leave_balances", {}))
        retrieved = {
            "source": "simulated_hr_store",
            "found": True,
            "employee_id": employee["employee_id"],
            "employment_status": employee.get("employment_status"),
            "annual_leave_balance": balances.get("annual"),
            "department": employee.get("department"),
            "manager": employee.get("manager"),
        }
        employee_data = employee
        summary = (
            f"Retrieved {employee['name']} ({employee_id}): "
            f"status={employee.get('employment_status')}, "
            f"annual_balance={balances.get('annual')}."
        )

    return node_update(
        "research",
        summary,
        employee_data=employee_data,
        retrieved_data=retrieved,
        errors=errors,
    )

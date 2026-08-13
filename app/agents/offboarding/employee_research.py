"""Offboarding employee research via employee tools only (no direct JSON)."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def offboarding_employee_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("offboarding_request") or {}
    entities = state.get("entities") or {}
    employee_id = str(request.get("employee_id") or entities.get("employee_id") or "")
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee: dict[str, Any] = {}

    if employee_id:
        emp_result, emp_patch = invoke_tool(
            state,
            agent="offboarding_employee_research",
            name="get_employee",
            payload={"employee_id": employee_id},
        )
        patches.append(emp_patch)
        if emp_result.success and emp_result.data:
            employee = dict(emp_result.data)
        else:
            errors.append(emp_result.error_message or f"Employee {employee_id} not found.")
    else:
        errors.append("Employee ID is required for offboarding research.")

    retrieved = {
        **(state.get("retrieved_data") or {}),
        "employment_status": employee.get("employment_status"),
        "department": employee.get("department"),
        "manager": employee.get("manager"),
        "joining_date": employee.get("joining_date"),
        "notice_period_days": employee.get("notice_period_days"),
    }
    entities = merge_entities(
        state,
        employee_id=employee.get("employee_id") or employee_id or None,
        department=employee.get("department") or None,
    )

    _, memory_patch = append_short_term(
        state,
        agent="offboarding_employee_research",
        content=(
            f"Retrieved employee {employee_id or 'unknown'} "
            f"status={employee.get('employment_status')} "
            f"dept={employee.get('department')} manager={employee.get('manager')}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "offboarding_employee_research",
        (
            f"Researched employee {employee_id or 'unknown'}: "
            f"status={employee.get('employment_status') or 'n/a'}."
        ),
        employee_data=employee or state.get("employee_data") or {},
        retrieved_data=retrieved,
        entities=entities,
        errors=errors,
        **combine_patches(*patches),
    )

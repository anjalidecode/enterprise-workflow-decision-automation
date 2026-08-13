"""Employee Research Agent: retrieve employee profile via tools."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def employee_research_agent(state: WorkflowState) -> dict[str, Any]:
    employee_id = (
        (state.get("entities") or {}).get("employee_id")
        or (state.get("metadata") or {}).get("onboarding_request", {}).get("employee_id")
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee_data: dict[str, Any] = {}

    if not employee_id:
        errors.append("Employee research skipped because no employee_id was resolved.")
    else:
        result, patch = invoke_tool(
            state,
            agent="employee_research",
            name="get_employee",
            payload={"employee_id": employee_id},
        )
        patches.append(patch)
        if result.success and result.data:
            employee_data = dict(result.data)
        else:
            errors.append(result.error_message or "get_employee failed.")

    entities = merge_entities(
        state,
        employee_id=employee_data.get("employee_id") or employee_id,
        department=employee_data.get("department"),
        role=employee_data.get("role"),
        manager=employee_data.get("manager"),
        joining_date=employee_data.get("joining_date"),
    )
    retrieved = dict(state.get("retrieved_data") or {})
    retrieved["employee"] = employee_data
    retrieved["employment_status"] = employee_data.get("employment_status")

    _, memory_patch = append_short_term(
        state,
        agent="employee_research",
        content=(
            f"Retrieved employee {employee_data.get('employee_id') or employee_id}: "
            f"role={employee_data.get('role')}, dept={employee_data.get('department')}, "
            f"status={employee_data.get('employment_status')}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "employee_research",
        (
            f"Retrieved employee {employee_data.get('employee_id') or 'unknown'} "
            f"({employee_data.get('employment_status') or 'n/a'})."
        ),
        entities=entities,
        employee_data=employee_data,
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )

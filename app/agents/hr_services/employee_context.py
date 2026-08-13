"""Employee Context: retrieve employee via existing tools; never read JSON directly."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def employee_context_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("hr_services_request") or {}
    entities = state.get("entities") or {}
    employee_id = str(request.get("employee_id") or entities.get("employee_id") or "")
    category = str(request.get("category") or (state.get("metadata") or {}).get("service_category") or "")
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee: dict[str, Any] = {}
    authorization: dict[str, Any] = {}

    # For knowledge-only / ticket categories, employee may be optional.
    needs_employee = category in {
        "leave_balance",
        "attendance",
        "employment_document",
        "onboarding",
    }

    # Prefer explicit employee id; otherwise map requester user_id when it looks like E###.
    if not employee_id:
        requester = str(state.get("user_id") or state.get("initiated_by") or "")
        if requester.upper().startswith("E") and len(requester) >= 4:
            employee_id = requester.upper()


    if employee_id:
        emp_result, emp_patch = invoke_tool(
            state,
            agent="employee_context",
            name="get_employee",
            payload={"employee_id": employee_id},
        )
        patches.append(emp_patch)
        if emp_result.success and emp_result.data:
            employee = dict(emp_result.data)
        else:
            errors.append(emp_result.error_message or f"Employee {employee_id} not found.")
    elif needs_employee:
        errors.append("Employee ID is required for this HR service request.")

    auth_result, auth_patch = invoke_tool(
        state,
        agent="employee_context",
        name="evaluate_hr_service_authorization",
        payload={
            "category": category or "general_hr",
            "target_employee_id": employee_id,
            "requester_user_id": state.get("user_id") or state.get("initiated_by") or "",
            "requester_role": state.get("user_role") or "",
            "candidate_id": str(request.get("candidate_id") or entities.get("candidate_id") or ""),
        },
    )
    patches.append(auth_patch)
    if auth_result.success and auth_result.data:
        authorization = dict(auth_result.data)
    else:
        errors.append(auth_result.error_message or "Authorization evaluation failed.")
        authorization = {
            "allowed": False,
            "reason": "Authorization evaluation failed.",
            "disclosure_blocked": True,
        }

    retrieved = {
        **(state.get("retrieved_data") or {}),
        "authorization": authorization,
        "employment_status": employee.get("employment_status"),
        "department": employee.get("department"),
        "manager": employee.get("manager"),
    }
    entities = merge_entities(
        state,
        employee_id=employee.get("employee_id") or employee_id or None,
        department=employee.get("department") or None,
    )
    metadata = {
        **state.get("metadata", {}),
        "authorization": authorization,
    }

    _, memory_patch = append_short_term(
        state,
        agent="employee_context",
        content=(
            f"Employee context employee={employee_id or 'n/a'} "
            f"auth_allowed={authorization.get('allowed')} "
            f"org={state.get('organization_id') or 'default'}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "employee_context",
        (
            f"Resolved employee context for {employee_id or 'n/a'}; "
            f"authorized={authorization.get('allowed')}."
        ),
        employee_data=employee or state.get("employee_data") or {},
        retrieved_data=retrieved,
        entities=entities,
        metadata=metadata,
        errors=errors,
        **combine_patches(*patches),
    )

"""Training employee research via tools only (no direct JSON access)."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def training_research_agent(state: WorkflowState) -> dict[str, Any]:
    request = (state.get("metadata") or {}).get("training_request") or {}
    entities = state.get("entities") or {}
    employee_id = str(request.get("employee_id") or entities.get("employee_id") or "")
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    employee: dict[str, Any] = {}
    history: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    role_requirements: list[dict[str, Any]] = []
    performance_records: list[dict[str, Any]] = []
    performance_skill_gaps: list[str] = []

    if employee_id:
        emp_result, emp_patch = invoke_tool(
            state,
            agent="training_research",
            name="get_employee",
            payload={"employee_id": employee_id},
        )
        patches.append(emp_patch)
        if emp_result.success and emp_result.data:
            employee = dict(emp_result.data)
        else:
            errors.append(emp_result.error_message or f"Employee {employee_id} not found.")

        hist_result, hist_patch = invoke_tool(
            state,
            agent="training_research",
            name="get_training_history",
            payload={"employee_id": employee_id},
        )
        patches.append(hist_patch)
        if hist_result.success and hist_result.data:
            history = list(hist_result.data.get("history") or [])
            skills = list(hist_result.data.get("skills") or [])
            role_requirements = list(hist_result.data.get("role_requirements") or [])
        else:
            errors.append(hist_result.error_message or "get_training_history failed.")

        perf_result, perf_patch = invoke_tool(
            state,
            agent="training_research",
            name="get_performance_records",
            payload={"employee_id": employee_id, "review_period": "2026-Q2"},
        )
        patches.append(perf_patch)
        if perf_result.success and perf_result.data:
            performance_records = list(perf_result.data.get("records") or [])
            if performance_records:
                performance_skill_gaps = list(performance_records[0].get("skill_gaps") or [])
    else:
        errors.append("Employee ID is required for training research.")

    retrieved = {
        **(state.get("retrieved_data") or {}),
        "training_history": history,
        "training_history_count": len(history),
        "employee_skills": skills,
        "role_requirements": role_requirements,
        "performance_records": performance_records,
        "performance_skill_gaps": performance_skill_gaps,
    }
    entities = merge_entities(
        state,
        employee_id=employee.get("employee_id") or employee_id or None,
        department=employee.get("department") or None,
    )

    _, memory_patch = append_short_term(
        state,
        agent="training_research",
        content=(
            f"Retrieved training history={len(history)} skills={len(skills)} "
            f"requirements={len(role_requirements)} for {employee_id or 'unknown'}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "training_research",
        (
            f"Researched training profile for {employee_id or 'unknown'}: "
            f"{len(history)} history record(s), {len(skills)} skill(s)."
        ),
        employee_data=employee or state.get("employee_data") or {},
        retrieved_data=retrieved,
        entities=entities,
        errors=errors,
        **combine_patches(*patches),
    )

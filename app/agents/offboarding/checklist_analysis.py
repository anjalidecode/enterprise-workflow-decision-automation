"""Checklist analysis: build structured exit checklist and identify blockers."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.tools.executor import invoke_tool


def checklist_analysis_agent(state: WorkflowState) -> dict[str, Any]:
    retrieved = state.get("retrieved_data") or {}
    employee = state.get("employee_data") or {}
    request = (state.get("metadata") or {}).get("offboarding_request") or {}
    employee_id = str(
        employee.get("employee_id")
        or request.get("employee_id")
        or (state.get("entities") or {}).get("employee_id")
        or ""
    )
    patches: list[dict[str, Any]] = []
    errors: list[str] = []
    checklist: dict[str, Any] = {}
    handover: dict[str, Any] = {}

    if employee_id:
        # Pull handover via checklist builder (store-backed). Also re-list assets if needed.
        checklist_result, checklist_patch = invoke_tool(
            state,
            agent="checklist_analysis",
            name="get_offboarding_checklist",
            payload={
                "employee_id": employee_id,
                "exit_record": dict(retrieved.get("exit_record") or {}),
                "assets": list(retrieved.get("assets") or []),
                "handover": dict(retrieved.get("handover") or {}),
                "workflow_id": state.get("workflow_id") or "",
            },
        )
        patches.append(checklist_patch)
        if checklist_result.success and checklist_result.data:
            checklist = dict(checklist_result.data)
        else:
            errors.append(checklist_result.error_message or "get_offboarding_checklist failed.")
    else:
        errors.append("Employee ID is required for checklist analysis.")
        checklist = {
            "employee_id": None,
            "items": [],
            "completed_tasks": [],
            "pending_tasks": [],
            "blockers": ["Employee ID missing for checklist generation."],
            "dependencies": {},
        }

    retrieved = {
        **retrieved,
        "checklist": checklist,
        "pending_checklist_tasks": list(checklist.get("pending_tasks") or []),
        "completed_checklist_tasks": list(checklist.get("completed_tasks") or []),
        "checklist_blockers": list(checklist.get("blockers") or []),
        "handover": handover or retrieved.get("handover") or {},
    }

    _, memory_patch = append_short_term(
        state,
        agent="checklist_analysis",
        content=(
            f"Checklist for {employee_id or 'unknown'}: "
            f"pending={len(checklist.get('pending_tasks') or [])} "
            f"blockers={len(checklist.get('blockers') or [])}."
        ),
    )
    patches.append(memory_patch)

    return node_update(
        "checklist_analysis",
        (
            f"Built exit checklist for {employee_id or 'unknown'}: "
            f"{len(checklist.get('pending_tasks') or [])} pending task(s)."
        ),
        retrieved_data=retrieved,
        errors=errors,
        **combine_patches(*patches),
    )

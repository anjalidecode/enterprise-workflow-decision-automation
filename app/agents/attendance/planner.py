"""Attendance Planner: parse request and plan attendance analysis tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.attendance_parser import parse_attendance_request

ATTENDANCE_TASKS = [
    "attendance_research",
    "attendance_analysis",
    "attendance_policy",
    "attendance_decision",
    "attendance_validation",
    "attendance_action",
    "attendance_response",
]


def attendance_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_attendance_request(state["user_request"])
    entities = merge_entities(
        state,
        employee_id=parsed.get("employee_id"),
        department=parsed.get("department"),
        start_date=parsed.get("start_date"),
        end_date=parsed.get("end_date"),
    )
    metadata = {
        **state.get("metadata", {}),
        "attendance_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "attendance"},
        agent="attendance_planner",
        content=(
            f"Attendance plan employee_id={parsed.get('employee_id') or 'scan'}; "
            f"range={parsed.get('start_date')}..{parsed.get('end_date')}; "
            f"scan_issues={parsed.get('scan_issues')}."
        ),
    )
    summary = (
        f"Planned attendance analysis for "
        f"employee_id={parsed.get('employee_id') or 'department/scan'}; "
        f"{parsed.get('month_label')}."
    )
    return node_update(
        "attendance_planner",
        summary,
        workflow_type="attendance",
        status="in_progress",
        tasks=list(ATTENDANCE_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

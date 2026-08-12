"""Planner Agent: parse the request and define the remaining work."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.leave_parser import parse_leave_request

LEAVE_TASKS = [
    "research",
    "policy",
    "analysis",
    "decision",
    "validation",
    "action",
    "response",
]


def planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_leave_request(state["user_request"])
    leave_request = parsed.model_dump()
    errors: list[str] = []

    if not parsed.employee_id:
        errors.append("Planner could not identify an employee id in the request.")
    if parsed.days is None:
        errors.append("Planner could not identify the number of leave days in the request.")
    if not parsed.start_date:
        errors.append("Planner could not identify a leave start date in the request.")

    summary = (
        f"Planned {len(LEAVE_TASKS)} tasks; parsed employee="
        f"{parsed.employee_id or 'unknown'}, days={parsed.days}, "
        f"start={parsed.start_date or 'unknown'}."
    )
    _, memory_patch = append_short_term(
        state,
        agent="planner",
        employee_id=parsed.employee_id,
        content=(
            f"Planner parsed employee {parsed.employee_id or 'unknown'} requesting "
            f"{parsed.days} annual leave days from {parsed.start_date or 'unknown'}."
        ),
    )

    return node_update(
        "planner",
        summary,
        tasks=list(LEAVE_TASKS),
        entities=merge_entities(
            state,
            employee_id=parsed.employee_id,
            leave_type=parsed.leave_type,
            days=parsed.days,
            start_date=parsed.start_date,
        ),
        errors=errors,
        metadata={
            **state.get("metadata", {}),
            "leave_request": leave_request,
        },
        **combine_patches(memory_patch),
    )

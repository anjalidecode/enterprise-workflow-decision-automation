"""Offboarding Planner: parse request and plan offboarding workflow tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.offboarding_parser import parse_offboarding_request

OFFBOARDING_TASKS = [
    "offboarding_employee_research",
    "exit_details_research",
    "checklist_analysis",
    "offboarding_policy",
    "offboarding_analysis",
    "offboarding_decision",
    "offboarding_validation",
    "offboarding_action",
    "offboarding_response",
]


def offboarding_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_offboarding_request(state["user_request"])
    entities = merge_entities(
        state,
        employee_id=parsed.get("employee_id"),
    )
    metadata = {
        **state.get("metadata", {}),
        "offboarding_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "offboarding"},
        agent="offboarding_planner",
        content=(
            f"Offboarding plan employee_id={parsed.get('employee_id') or 'missing'}; "
            f"operation={parsed.get('operation')}; exit_type={parsed.get('exit_type')}."
        ),
    )
    summary = (
        f"Planned offboarding {parsed.get('operation')} for "
        f"employee_id={parsed.get('employee_id') or 'unknown'}."
    )
    return node_update(
        "offboarding_planner",
        summary,
        workflow_type="offboarding",
        status="in_progress",
        tasks=list(OFFBOARDING_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

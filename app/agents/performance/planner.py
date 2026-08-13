"""Performance Planner: parse request and plan performance analysis tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.performance_parser import parse_performance_request

PERFORMANCE_TASKS = [
    "performance_research",
    "goal_analysis",
    "performance_analysis",
    "performance_policy",
    "performance_decision",
    "performance_validation",
    "performance_action",
    "performance_response",
]


def performance_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_performance_request(state["user_request"])
    entities = merge_entities(
        state,
        employee_id=parsed.get("employee_id"),
        review_period=parsed.get("review_period"),
    )
    metadata = {
        **state.get("metadata", {}),
        "performance_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "performance"},
        agent="performance_planner",
        content=(
            f"Performance plan employee_id={parsed.get('employee_id') or 'scan'}; "
            f"period={parsed.get('review_period')}; "
            f"operation={parsed.get('operation')}; "
            f"scan_support={parsed.get('scan_support')}."
        ),
    )
    summary = (
        f"Planned performance {parsed.get('operation')} for "
        f"employee_id={parsed.get('employee_id') or 'org scan'}; "
        f"{parsed.get('period_label')}."
    )
    return node_update(
        "performance_planner",
        summary,
        workflow_type="performance",
        status="in_progress",
        tasks=list(PERFORMANCE_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

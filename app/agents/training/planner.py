"""Training Planner: parse request and plan training workflow tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.training_parser import parse_training_request

TRAINING_TASKS = [
    "training_research",
    "skill_gap_analysis",
    "training_catalog_research",
    "training_policy",
    "training_analysis",
    "training_decision",
    "training_validation",
    "training_action",
    "training_response",
]


def training_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_training_request(state["user_request"])
    entities = merge_entities(
        state,
        employee_id=parsed.get("employee_id"),
    )
    metadata = {
        **state.get("metadata", {}),
        "training_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "training"},
        agent="training_planner",
        content=(
            f"Training plan employee_id={parsed.get('employee_id') or 'missing'}; "
            f"operation={parsed.get('operation')}."
        ),
    )
    summary = (
        f"Planned training {parsed.get('operation')} for "
        f"employee_id={parsed.get('employee_id') or 'unknown'}."
    )
    return node_update(
        "training_planner",
        summary,
        workflow_type="training",
        status="in_progress",
        tasks=list(TRAINING_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

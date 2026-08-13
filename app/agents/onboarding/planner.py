"""Onboarding Planner: parse request and plan onboarding tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.onboarding_parser import parse_onboarding_request

ONBOARDING_TASKS = [
    "employee_research",
    "document_verification",
    "onboarding_policy",
    "onboarding_analysis",
    "onboarding_decision",
    "onboarding_validation",
    "onboarding_action",
    "onboarding_response",
]


def onboarding_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_onboarding_request(state["user_request"])
    entities = merge_entities(state, employee_id=parsed.get("employee_id"))
    metadata = {
        **state.get("metadata", {}),
        "onboarding_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "onboarding"},
        agent="onboarding_planner",
        content=(
            f"Onboarding plan for employee_id={parsed.get('employee_id') or 'unknown'}; "
            f"tasks={len(ONBOARDING_TASKS)}."
        ),
    )
    summary = (
        f"Planned onboarding for employee_id={parsed.get('employee_id') or 'unresolved'}; "
        f"{len(ONBOARDING_TASKS)} tasks."
    )
    return node_update(
        "onboarding_planner",
        summary,
        workflow_type="onboarding",
        status="in_progress",
        tasks=list(ONBOARDING_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

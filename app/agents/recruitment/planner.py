"""Recruitment Planner: parse request and plan recruitment tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.recruitment_parser import parse_recruitment_request

RECRUITMENT_TASKS = [
    "job_research",
    "candidate_research",
    "candidate_analysis",
    "candidate_scoring",
    "recruitment_policy",
    "recruitment_decision",
    "recruitment_validation",
    "recruitment_action",
    "recruitment_response",
]


def recruitment_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_recruitment_request(state["user_request"])
    entities = merge_entities(
        state,
        job_id=parsed.get("job_id"),
        query=parsed.get("query"),
    )
    metadata = {
        **state.get("metadata", {}),
        "recruitment_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "recruitment"},
        agent="recruitment_planner",
        content=(
            f"Recruitment plan for job_id={parsed.get('job_id') or 'unknown'}; "
            f"tasks={len(RECRUITMENT_TASKS)}."
        ),
    )
    summary = (
        f"Planned recruitment for job_id={parsed.get('job_id') or 'unresolved'}; "
        f"{len(RECRUITMENT_TASKS)} tasks."
    )
    return node_update(
        "recruitment_planner",
        summary,
        workflow_type="recruitment",
        status="in_progress",
        tasks=list(RECRUITMENT_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

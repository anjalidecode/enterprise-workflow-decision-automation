"""HR Services Planner: parse request and plan workflow tasks."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, merge_entities, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.hr_services_parser import parse_hr_services_request

HR_SERVICES_TASKS = [
    "request_classification",
    "employee_context",
    "service_research",
    "service_policy",
    "service_analysis",
    "service_decision",
    "service_validation",
    "service_action",
    "service_response",
]


def hr_services_planner_agent(state: WorkflowState) -> dict[str, Any]:
    parsed = parse_hr_services_request(state["user_request"])
    entities = merge_entities(
        state,
        employee_id=parsed.get("employee_id"),
        candidate_id=parsed.get("candidate_id"),
    )
    metadata = {
        **state.get("metadata", {}),
        "hr_services_request": parsed,
    }
    _, memory_patch = append_short_term(
        {**state, "entities": entities, "workflow_type": "hr_services"},
        agent="hr_services_planner",
        content=(
            f"HR services plan employee_id={parsed.get('employee_id') or 'missing'}; "
            f"category_hint={parsed.get('category')}; operation={parsed.get('operation')}."
        ),
    )
    summary = (
        f"Planned HR services {parsed.get('operation')} "
        f"category_hint={parsed.get('category')} "
        f"employee_id={parsed.get('employee_id') or 'unknown'}."
    )
    return node_update(
        "hr_services_planner",
        summary,
        workflow_type="hr_services",
        status="in_progress",
        tasks=list(HR_SERVICES_TASKS),
        entities=entities,
        metadata=metadata,
        **combine_patches(memory_patch),
    )

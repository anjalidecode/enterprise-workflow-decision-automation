"""Request Classification: deterministic HR service category classification."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState
from app.services.hr_services_parser import (
    SERVICE_CATEGORIES,
    classify_hr_service_category,
    parse_hr_services_request,
)


def request_classification_agent(state: WorkflowState) -> dict[str, Any]:
    request = dict((state.get("metadata") or {}).get("hr_services_request") or {})
    if not request:
        request = parse_hr_services_request(state["user_request"])

    category = classify_hr_service_category(state["user_request"])
    if category not in SERVICE_CATEGORIES:
        category = "general_hr"

    request = {**request, "category": category}
    metadata = {
        **state.get("metadata", {}),
        "hr_services_request": request,
        "service_category": category,
    }

    _, memory_patch = append_short_term(
        state,
        agent="request_classification",
        content=f"Classified HR service category={category}.",
    )

    return node_update(
        "request_classification",
        f"Classified request as {category}.",
        metadata=metadata,
        **combine_patches(memory_patch),
    )

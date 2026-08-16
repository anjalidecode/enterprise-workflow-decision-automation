"""Orchestrator Agent: identify the workflow type and start the run."""

from __future__ import annotations

from typing import Any

from app.agents.common import combine_patches, node_update
from app.memory.facade import append_short_term
from app.orchestration.state import WorkflowState

LEAVE_KEYWORDS = ("leave", "time off", "pto", "vacation", "attendance")


def orchestrator_agent(state: WorkflowState) -> dict[str, Any]:
    existing = (state.get("workflow_type") or "").strip()
    request = state["user_request"].lower()
    is_leave = existing == "leave_attendance" or any(keyword in request for keyword in LEAVE_KEYWORDS)

    if is_leave:
        workflow_type = "leave_attendance"
        status = "in_progress"
        summary = "Classified request as leave_attendance and started the workflow."
        errors: list[str] = []
    else:
        workflow_type = existing or "unsupported"
        status = "in_progress"
        summary = "Request is not a leave & attendance workflow; marking as unsupported."
        errors = ["Unsupported workflow type for Module 1. Only leave & attendance is available."]

    _, memory_patch = append_short_term(
        {**state, "workflow_type": workflow_type},
        agent="orchestrator",
        workflow_type=workflow_type,
        content=f"Workflow started as {workflow_type}.",
    )

    return node_update(
        "orchestrator",
        summary,
        workflow_type=workflow_type,
        status=status,
        errors=errors,
        metadata={
            **state.get("metadata", {}),
            "identified_by": "orchestrator",
        },
        **combine_patches(memory_patch),
    )

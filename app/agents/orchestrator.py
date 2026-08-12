"""Orchestrator Agent: identify the workflow type and start the run."""

from __future__ import annotations

from typing import Any

from app.agents.common import node_update
from app.orchestration.state import WorkflowState

LEAVE_KEYWORDS = ("leave", "time off", "pto", "vacation", "attendance")


def orchestrator_agent(state: WorkflowState) -> dict[str, Any]:
    request = state["user_request"].lower()
    is_leave = any(keyword in request for keyword in LEAVE_KEYWORDS)

    if is_leave:
        workflow_type = "leave_attendance"
        status = "in_progress"
        summary = "Classified request as leave_attendance and started the workflow."
        errors: list[str] = []
    else:
        workflow_type = "unsupported"
        status = "in_progress"
        summary = "Request is not a leave & attendance workflow; marking as unsupported."
        errors = ["Unsupported workflow type for Module 1. Only leave & attendance is available."]

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
    )

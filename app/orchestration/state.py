"""Shared LangGraph state for HR workflow runs.

WorkflowState is the live coordination contract for every workflow type.
Optional organization/user fields prepare multi-company tenancy without
requiring authentication or PostgreSQL in Module 1.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from operator import add
from typing import Annotated, Any, TypedDict


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentOutput(TypedDict):
    """One agent's contribution to the workflow trace."""

    agent: str
    summary: str
    timestamp: str


class WorkflowState(TypedDict):
    """Structured state shared by every agent node in a workflow run."""

    workflow_id: str
    request_id: str
    user_request: str
    workflow_type: str
    organization_id: str
    user_id: str
    initiated_by: str
    user_role: str
    current_stage: str
    status: str
    tasks: list[str]
    completed_tasks: Annotated[list[str], add]
    # Leave workflow continues to use employee_data. entities is the reusable
    # cross-workflow context bag (employee_id, candidate_id, job_id, ...).
    entities: dict[str, Any]
    employee_data: dict[str, Any]
    retrieved_data: dict[str, Any]
    policy_results: dict[str, Any]
    analysis_results: dict[str, Any]
    decision: dict[str, Any]
    confidence: float
    pending_actions: list[dict[str, Any]]
    completed_actions: Annotated[list[dict[str, Any]], add]
    errors: Annotated[list[str], add]
    requires_human_approval: bool
    agent_outputs: Annotated[list[AgentOutput], add]
    tool_executions: Annotated[list[dict[str, Any]], add]
    memory_accesses: Annotated[list[dict[str, Any]], add]
    metadata: dict[str, Any]
    created_at: str
    final_response: str


def create_initial_state(
    user_request: str,
    *,
    organization_id: str = "",
    user_id: str = "",
    initiated_by: str = "",
    user_role: str = "",
    request_id: str | None = None,
    entities: dict[str, Any] | None = None,
    workflow_type: str = "",
) -> WorkflowState:
    """Build a blank workflow state for a new user request.

    Organization and user fields are optional placeholders for future tenancy
    and authentication. Existing callers that only pass user_request remain valid.
    """

    workflow_id = str(uuid.uuid4())
    return WorkflowState(
        workflow_id=workflow_id,
        request_id=request_id or workflow_id,
        user_request=user_request,
        workflow_type=workflow_type,
        organization_id=organization_id,
        user_id=user_id,
        initiated_by=initiated_by or user_id,
        user_role=user_role,
        current_stage="start",
        status="pending",
        tasks=[],
        completed_tasks=[],
        entities=dict(entities or {}),
        employee_data={},
        retrieved_data={},
        policy_results={},
        analysis_results={},
        decision={},
        confidence=0.0,
        pending_actions=[],
        completed_actions=[],
        errors=[],
        requires_human_approval=False,
        agent_outputs=[],
        tool_executions=[],
        memory_accesses=[],
        metadata={},
        created_at=_utc_now(),
        final_response="",
    )

"""Shared LangGraph state for HR workflow runs."""

from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, Any, TypedDict


class AgentOutput(TypedDict):
    """One agent's contribution to the workflow trace."""

    agent: str
    summary: str
    timestamp: str


class WorkflowState(TypedDict):
    """Structured state shared by every agent node in a workflow run."""

    workflow_id: str
    user_request: str
    workflow_type: str
    current_stage: str
    status: str
    tasks: list[str]
    completed_tasks: Annotated[list[str], add]
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
    metadata: dict[str, Any]
    final_response: str


def create_initial_state(user_request: str) -> WorkflowState:
    """Build a blank workflow state for a new user request."""

    return WorkflowState(
        workflow_id=str(uuid.uuid4()),
        user_request=user_request,
        workflow_type="",
        current_stage="start",
        status="pending",
        tasks=[],
        completed_tasks=[],
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
        metadata={},
        final_response="",
    )

"""Workflow platform contracts: specs, routing results, audits, metrics."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.orchestration.state import WorkflowState

RouterStatus = Literal["routed", "unsupported", "needs_clarification"]


class WorkflowSpec(BaseModel):
    """Declarative contract for one registered HR workflow."""

    workflow_type: str
    name: str
    description: str
    supported_request_hints: list[str] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    required_tool_capabilities: list[str] = Field(default_factory=list)
    memory_profile: dict[str, Any] = Field(default_factory=dict)
    entry_node: str = "orchestrator"
    terminal_statuses: list[str] = Field(default_factory=list)
    approval_outcomes: list[str] = Field(default_factory=list)
    version: str = "1.0"


class RouterResult(BaseModel):
    """Deterministic classification result from WorkflowRouter."""

    workflow_type: str = ""
    confidence: float = 0.0
    matched_hints: list[str] = Field(default_factory=list)
    unsupported_reason: str = ""
    status: RouterStatus = "unsupported"


class ApprovalDecision(BaseModel):
    """Human decision used to resume a paused workflow."""

    approved: bool
    decided_by: str = ""
    comment: str = ""


class WorkflowAuditSnapshot(BaseModel):
    """Stable audit view derived from WorkflowState traces (no secrets)."""

    workflow_id: str = ""
    organization_id: str = ""
    workflow_type: str = ""
    started_at: str = ""
    completed_at: str = ""
    status: str = ""
    final_outcome: str = ""
    agents_executed: list[dict[str, Any]] = Field(default_factory=list)
    tool_executions: list[dict[str, Any]] = Field(default_factory=list)
    memory_accesses: list[dict[str, Any]] = Field(default_factory=list)
    decision: dict[str, Any] = Field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    completed_actions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    approval_checkpoint: dict[str, Any] | None = None
    llm: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunMetrics(BaseModel):
    """Run metrics derived from workflow traces."""

    duration_ms: float = 0.0
    agent_count: int = 0
    tool_count: int = 0
    tool_success_rate: float = 0.0
    retry_count: int = 0
    validation_failed: bool = False
    human_approval_required: bool = False
    decision_confidence: float = 0.0
    action_success_rate: float = 0.0
    escalated: bool = False
    workflow_type: str = ""
    organization_id: str = ""
    status: str = ""


class WorkflowResult(BaseModel):
    """Engine return value: final state plus audit and metrics."""

    model_config = {"arbitrary_types_allowed": True}

    state: dict[str, Any]
    audit: WorkflowAuditSnapshot
    metrics: WorkflowRunMetrics
    router: RouterResult | None = None
    spec_version: str = ""

    @property
    def workflow_state(self) -> WorkflowState:
        return self.state  # type: ignore[return-value]

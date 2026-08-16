"""Workflow API request/response schemas (stable HTTP contract)."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class WorkflowRunRequest(BaseModel):
    """Authenticated workflow run body.

    Identity (user_id / organization_id / role) comes from the JWT only.
    Extra identity fields in the JSON body are ignored and never trusted.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    request: str = Field(
        ...,
        min_length=1,
        description="Natural-language business request",
        validation_alias=AliasChoices("request", "request_text"),
    )
    workflow_type: str | None = Field(
        default=None,
        description="Optional explicit workflow_type; otherwise automatic routing is used",
    )

    @field_validator("request")
    @classmethod
    def request_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("request must be a non-empty string")
        return cleaned


class WorkflowDecisionResponse(BaseModel):
    outcome: str = ""
    rationale: str = ""
    confidence: float = 0.0
    requires_human_approval: bool = False
    executable: bool = False
    entity_refs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowTypeItem(BaseModel):
    workflow_type: str
    name: str
    description: str
    version: str = "1.0"


class WorkflowTypeResponse(BaseModel):
    workflows: list[WorkflowTypeItem]


class WorkflowAuditResponse(BaseModel):
    workflow_id: str = ""
    organization_id: str = ""
    workflow_type: str = ""
    started_at: str = ""
    completed_at: str = ""
    status: str = ""
    final_outcome: str = ""
    agents: list[dict[str, Any]] = Field(default_factory=list)
    tool_executions: list[dict[str, Any]] = Field(default_factory=list)
    memory_accesses: list[dict[str, Any]] = Field(default_factory=list)
    decision: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    approval_checkpoint: dict[str, Any] | None = None
    llm: dict[str, Any] = Field(default_factory=dict)


class RequestUnderstandingResponse(BaseModel):
    intent: str = ""
    workflow_type: str = ""
    request_kind: str = ""
    summary_label: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)


class WorkflowMetricsResponse(BaseModel):
    duration_ms: float = 0.0
    agent_count: int = 0
    tool_count: int = 0
    tool_success_rate: float = 0.0
    retry_count: int = 0
    action_count: int = 0
    action_success_rate: float = 0.0
    validation_failed: bool = False
    human_approval_required: bool = False
    decision_confidence: float = 0.0
    escalated: bool = False
    workflow_type: str = ""
    organization_id: str = ""
    status: str = ""
    success: bool = False


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    workflow_type: str = ""
    status: str = ""
    current_stage: str = ""
    organization_id: str = ""
    decision: WorkflowDecisionResponse | None = None
    response: str = ""
    actions: list[dict[str, Any]] = Field(default_factory=list)
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    approval_status: str | None = None
    audit: WorkflowAuditResponse | None = None
    metrics: WorkflowMetricsResponse | None = None
    router_status: str | None = None
    request_id: str = ""
    understanding: RequestUnderstandingResponse | None = None


class WorkflowSummary(BaseModel):
    workflow_id: str
    workflow_type: str = ""
    status: str = ""
    organization_id: str = ""
    created_at: str = ""
    outcome: str = ""
    approval_status: str | None = None


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowSummary]
    total: int
    limit: int
    offset: int
    note: str = (
        "Persisted workflow runs from PostgreSQL for the authenticated organization, "
        "filtered by role-aware ownership rules."
    )

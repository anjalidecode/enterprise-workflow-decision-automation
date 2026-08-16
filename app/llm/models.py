"""Pydantic contracts for LLM calls and request understanding."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

LLMProviderName = Literal["gemini", "deterministic_fallback", "none"]
RequestKind = Literal["action", "information", "unsupported"]
LLMOperation = Literal["understand", "respond"]


class LLMUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMCallResult(BaseModel):
    """Safe, loggable result of one LLM invocation."""

    provider: LLMProviderName = "none"
    model: str = ""
    operation: LLMOperation = "understand"
    status: str = "skipped"
    duration_ms: float = 0.0
    usage: LLMUsage = Field(default_factory=LLMUsage)
    error_type: str = ""
    text: str = ""
    parsed: dict[str, Any] = Field(default_factory=dict)


class UnderstandingEntities(BaseModel):
    """Entities extracted for routing and workflow initialization only."""

    employee_id: str | None = None
    job_id: str | None = None
    dates: list[str] = Field(default_factory=list)
    duration_days: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None
    skills: list[str] = Field(default_factory=list)
    job_title: str | None = None
    query: str | None = None

    @field_validator("employee_id", "job_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("duration_days", mode="before")
    @classmethod
    def _duration(cls, value: Any) -> Any:
        if value in (None, "", []):
            return None
        try:
            days = int(value)
        except (TypeError, ValueError):
            return None
        return days if days > 0 else None


class LLMUnderstandingSchema(BaseModel):
    """Schema sent to Gemini — excludes provider so the model cannot claim fallback."""

    intent: str = "unknown"
    workflow_type: str = ""
    request_kind: RequestKind = "action"
    entities: UnderstandingEntities = Field(default_factory=UnderstandingEntities)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    reason: str = ""
    summary_label: str = ""


class RequestUnderstanding(BaseModel):
    """Structured interpretation used before WorkflowRouter.

    Never execute enterprise actions from this object without validation.
    """

    intent: str = "unknown"
    workflow_type: str = ""
    request_kind: RequestKind = "action"
    entities: UnderstandingEntities = Field(default_factory=UnderstandingEntities)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    reason: str = ""
    summary_label: str = ""
    provider: LLMProviderName = "deterministic_fallback"

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return float(value)


class RequestUnderstandingPublic(BaseModel):
    """HR-facing understanding — no provider internals."""

    intent: str = ""
    workflow_type: str = ""
    request_kind: RequestKind = "action"
    summary_label: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    """Minimum authenticated context for understanding. No secrets."""

    role: str = ""
    employee_id: str = ""
    organization_id: str = ""
    user_id: str = ""


class GroundedResponseInput(BaseModel):
    """Facts the response model may use — nothing else."""

    workflow_type: str = ""
    status: str = ""
    outcome: str = ""
    rationale: str = ""
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    deterministic_response: str = ""

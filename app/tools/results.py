"""Common result returned by the tool executor."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ErrorCode = Literal["NOT_FOUND", "INVALID_INPUT", "SERVICE_ERROR", "FORBIDDEN"]


class ToolResult(BaseModel):
    """Normalized outcome of one tool execution attempt sequence."""

    tool_name: str
    success: bool
    data: dict[str, Any] | None = None
    error_code: ErrorCode | None = None
    error_message: str | None = None
    retryable: bool = False
    attempts: int = 1
    duration_ms: float = 0.0
    source: str = "simulated_hr_store"


class ToolExecutionRecord(BaseModel):
    """Safe, append-only trace entry stored on WorkflowState."""

    tool_name: str
    agent: str
    capability: str
    success: bool
    attempts: int
    duration_ms: float
    error_code: str | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    workflow_id: str = ""
    organization_id: str = ""
    user_id: str = ""

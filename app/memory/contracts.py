"""Typed memory records and access traces."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MemoryLayer = Literal["short_term", "knowledge", "long_term"]
MemoryKind = Literal["observation", "retrieval", "outcome", "influence"]
MemoryOperation = Literal["read", "write"]


class MemoryRecord(BaseModel):
    """One item stored in short-term, knowledge, or long-term memory."""

    memory_id: str
    layer: MemoryLayer
    kind: MemoryKind
    workflow_id: str | None = None
    employee_id: str | None = None
    workflow_type: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str


class MemoryAccess(BaseModel):
    """Safe trace of a memory read or write for WorkflowState and the CLI."""

    agent: str
    operation: MemoryOperation
    layer: MemoryLayer
    memory_ids: list[str] = Field(default_factory=list)
    summary: str
    influenced_decision: bool = False

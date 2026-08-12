"""Memory store ports. Agents use MemoryFacade, never these implementations directly.

JSONL / in-process stores are development backends. Module 5 may swap in PostgreSQL
without changing agent code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.memory.contracts import MemoryKind, MemoryRecord


@runtime_checkable
class ShortTermMemoryPort(Protocol):
    def append(
        self,
        *,
        workflow_id: str,
        content: str,
        kind: MemoryKind = "observation",
        agent: str | None = None,
        organization_id: str = "",
        user_id: str | None = None,
        employee_id: str | None = None,
        workflow_type: str | None = None,
        metadata: dict | None = None,
    ) -> MemoryRecord: ...

    def list_for_workflow(
        self,
        workflow_id: str,
        *,
        organization_id: str = "",
    ) -> list[MemoryRecord]: ...

    def reset(self) -> None: ...


@runtime_checkable
class LongTermMemoryPort(Protocol):
    def write(self, payload: dict) -> MemoryRecord: ...

    def query(
        self,
        *,
        employee_id: str,
        organization_id: str = "",
        workflow_type: str | None = None,
    ) -> list[MemoryRecord]: ...

    def reset(self) -> None: ...

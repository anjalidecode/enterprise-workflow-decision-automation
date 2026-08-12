"""Workflow-scoped in-process short-term memory. Not persisted.

Scoped by organization_id + workflow_id so multi-tenant runs never share a notebook.
Empty organization_id preserves the current single-tenant development behavior.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from app.memory.contracts import MemoryKind, MemoryRecord


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope_key(organization_id: str, workflow_id: str) -> str:
    return f"{organization_id or '_'}::{workflow_id}"


class ShortTermMemory:
    """Notebook for a single workflow run, keyed by organization + workflow."""

    def __init__(self) -> None:
        self._records: dict[str, list[MemoryRecord]] = defaultdict(list)

    def reset(self) -> None:
        self._records.clear()

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
    ) -> MemoryRecord:
        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            layer="short_term",
            kind=kind,
            workflow_id=workflow_id,
            organization_id=organization_id or "",
            user_id=user_id,
            employee_id=employee_id,
            workflow_type=workflow_type,
            content=content,
            metadata={"agent": agent, **(metadata or {})},
            timestamp=_utc_now(),
        )
        self._records[_scope_key(organization_id, workflow_id)].append(record)
        return record

    def list_for_workflow(
        self,
        workflow_id: str,
        *,
        organization_id: str = "",
    ) -> list[MemoryRecord]:
        return list(self._records.get(_scope_key(organization_id, workflow_id), []))


_STORE: ShortTermMemory | None = None


def get_short_term_store() -> ShortTermMemory:
    global _STORE
    if _STORE is None:
        _STORE = ShortTermMemory()
    return _STORE


def reset_short_term() -> ShortTermMemory:
    store = get_short_term_store()
    store.reset()
    return store

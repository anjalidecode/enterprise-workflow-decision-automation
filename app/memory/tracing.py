"""Helpers that append MemoryAccess records onto WorkflowState patches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.memory.contracts import MemoryAccess, MemoryLayer, MemoryOperation


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_access_patch(
    *,
    agent: str,
    operation: MemoryOperation,
    layer: MemoryLayer,
    memory_ids: list[str],
    summary: str,
    influenced_decision: bool = False,
    organization_id: str = "",
    workflow_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    access = MemoryAccess(
        agent=agent,
        operation=operation,
        layer=layer,
        memory_ids=memory_ids,
        summary=summary,
        influenced_decision=influenced_decision,
        organization_id=organization_id,
        workflow_id=workflow_id,
        user_id=user_id,
        timestamp=_utc_now(),
    )
    return {"memory_accesses": [access.model_dump()]}


def merge_memory_patches(*patches: dict[str, Any]) -> dict[str, Any]:
    accesses: list[dict[str, Any]] = []
    for patch in patches:
        accesses.extend(patch.get("memory_accesses") or [])
    return {"memory_accesses": accesses} if accesses else {}

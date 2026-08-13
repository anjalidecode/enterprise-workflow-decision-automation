"""API-layer in-memory index of WorkflowResult objects for this process.

Not durable storage. Lost on process restart. Organization-aware: callers must
supply organization_id; cross-organization lookups return not-found.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.workflows.contracts import WorkflowResult


@dataclass
class ExecutionIndex:
    """Process-local index of workflow runs returned through the API."""

    _by_id: dict[str, WorkflowResult] = field(default_factory=dict)

    def put(self, result: WorkflowResult) -> None:
        workflow_id = str((result.state or {}).get("workflow_id") or "")
        if not workflow_id:
            return
        self._by_id[workflow_id] = result

    def get(self, workflow_id: str, *, organization_id: str) -> WorkflowResult | None:
        result = self._by_id.get(workflow_id)
        if result is None:
            return None
        result_org = str((result.state or {}).get("organization_id") or "")
        if result_org != organization_id:
            # Do not leak existence across organizations.
            return None
        return result

    def list(
        self,
        *,
        organization_id: str,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WorkflowResult], int]:
        items: list[WorkflowResult] = []
        for result in self._by_id.values():
            state: dict[str, Any] = result.state or {}
            if str(state.get("organization_id") or "") != organization_id:
                continue
            if workflow_type and str(state.get("workflow_type") or "") != workflow_type:
                continue
            if status and str(state.get("status") or "") != status:
                continue
            items.append(result)

        # Newest first by created_at when available.
        items.sort(
            key=lambda item: str((item.state or {}).get("created_at") or ""),
            reverse=True,
        )
        total = len(items)
        sliced = items[offset : offset + limit]
        return sliced, total

    def clear(self) -> None:
        self._by_id.clear()


_INDEX: ExecutionIndex | None = None


def get_execution_index() -> ExecutionIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = ExecutionIndex()
    return _INDEX


def reset_execution_index() -> ExecutionIndex:
    global _INDEX
    _INDEX = ExecutionIndex()
    return _INDEX

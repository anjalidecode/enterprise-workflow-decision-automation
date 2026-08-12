"""Single memory API for agents. Enforces permissions and records accesses."""

from __future__ import annotations

from typing import Any

from app.knowledge.contracts import KnowledgeHit
from app.knowledge.store import get_knowledge_store, reset_knowledge_store
from app.memory.contracts import MemoryKind, MemoryLayer, MemoryRecord
from app.memory.errors import MemoryPermissionError
from app.memory.long_term import get_long_term_store, reset_long_term
from app.memory.short_term import get_short_term_store, reset_short_term
from app.memory.tracing import memory_access_patch
from app.orchestration.state import WorkflowState

AGENT_MEMORY_PERMISSIONS: dict[str, dict[MemoryLayer, set[str]]] = {
    "orchestrator": {"short_term": {"write"}},
    "planner": {"short_term": {"write"}},
    "research": {"short_term": {"read", "write"}, "long_term": {"read"}},
    "policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "analysis": {
        "short_term": {"read", "write"},
        "knowledge": {"read"},
        "long_term": {"read"},
    },
    "decision": {
        "short_term": {"read", "write"},
        "knowledge": {"read"},
        "long_term": {"read"},
    },
    "validation": {"short_term": {"read"}},
    "action": {"short_term": {"write"}},
    "response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
}


def _require(agent: str, layer: MemoryLayer, operation: str) -> None:
    allowed = AGENT_MEMORY_PERMISSIONS.get(agent, {}).get(layer, set())
    if operation not in allowed:
        raise MemoryPermissionError(
            f"Agent '{agent}' is not allowed to {operation} {layer} memory."
        )


def _context(state: WorkflowState) -> tuple[str, str | None, str | None]:
    leave_request = (state.get("metadata") or {}).get("leave_request") or {}
    employee_id = leave_request.get("employee_id") or (state.get("employee_data") or {}).get(
        "employee_id"
    )
    return state.get("workflow_id", ""), employee_id, state.get("workflow_type") or None


def append_short_term(
    state: WorkflowState,
    *,
    agent: str,
    content: str,
    kind: MemoryKind = "observation",
    workflow_type: str | None = None,
    employee_id: str | None = None,
    influenced_decision: bool = False,
) -> tuple[MemoryRecord, dict[str, Any]]:
    _require(agent, "short_term", "write")
    workflow_id, default_employee, default_type = _context(state)
    record = get_short_term_store().append(
        workflow_id=workflow_id,
        content=content,
        kind=kind,
        agent=agent,
        employee_id=employee_id or default_employee,
        workflow_type=workflow_type or default_type,
    )
    patch = memory_access_patch(
        agent=agent,
        operation="write",
        layer="short_term",
        memory_ids=[record.memory_id],
        summary=content[:180],
        influenced_decision=influenced_decision,
    )
    return record, patch


def search_short_term(
    state: WorkflowState,
    *,
    agent: str,
) -> tuple[list[MemoryRecord], dict[str, Any]]:
    _require(agent, "short_term", "read")
    workflow_id, _, _ = _context(state)
    records = get_short_term_store().list_for_workflow(workflow_id)
    patch = memory_access_patch(
        agent=agent,
        operation="read",
        layer="short_term",
        memory_ids=[item.memory_id for item in records],
        summary=f"Read {len(records)} short-term note(s) for this workflow.",
    )
    return records, patch


def search_knowledge(
    state: WorkflowState,
    *,
    agent: str,
    query: str,
    workflow_type: str | None = None,
    doc_type: str | None = "handbook",
) -> tuple[list[KnowledgeHit], dict[str, Any]]:
    _require(agent, "knowledge", "read")
    _, _, default_type = _context(state)
    hits = get_knowledge_store().search(
        query,
        workflow_type=workflow_type or default_type,
        doc_type=doc_type,
    )
    patch = memory_access_patch(
        agent=agent,
        operation="read",
        layer="knowledge",
        memory_ids=[hit.document_id for hit in hits],
        summary=f"Retrieved {len(hits)} knowledge passage(s) for query.",
    )
    return hits, patch


def recall_long_term(
    state: WorkflowState,
    *,
    agent: str,
    employee_id: str | None = None,
    workflow_type: str | None = None,
) -> tuple[list[MemoryRecord], dict[str, Any]]:
    _require(agent, "long_term", "read")
    _, default_employee, default_type = _context(state)
    target_employee = employee_id or default_employee
    if not target_employee:
        patch = memory_access_patch(
            agent=agent,
            operation="read",
            layer="long_term",
            memory_ids=[],
            summary="Skipped long-term recall; no employee id.",
        )
        return [], patch
    records = get_long_term_store().query(
        employee_id=str(target_employee),
        workflow_type=workflow_type or default_type,
    )
    patch = memory_access_patch(
        agent=agent,
        operation="read",
        layer="long_term",
        memory_ids=[item.memory_id for item in records],
        summary=f"Recalled {len(records)} long-term outcome(s) for {target_employee}.",
    )
    return records, patch


def write_long_term(
    state: WorkflowState,
    *,
    agent: str,
    payload: dict[str, Any],
) -> tuple[MemoryRecord, dict[str, Any]]:
    _require(agent, "long_term", "write")
    workflow_id, employee_id, workflow_type = _context(state)
    record = get_long_term_store().write(
        {
            "workflow_id": workflow_id,
            "employee_id": employee_id,
            "workflow_type": workflow_type,
            **payload,
        }
    )
    patch = memory_access_patch(
        agent=agent,
        operation="write",
        layer="long_term",
        memory_ids=[record.memory_id],
        summary="Wrote compact long-term workflow outcome.",
    )
    return record, patch


def reset_memory() -> None:
    """Reset all memory layers. Used by tests."""

    reset_short_term()
    reset_long_term()
    reset_knowledge_store()


def reset_short_term_memory() -> None:
    """Clear the current-run notebook. Does not touch long-term memory."""

    reset_short_term()

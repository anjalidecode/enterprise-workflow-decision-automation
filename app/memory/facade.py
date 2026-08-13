"""Single memory API for agents. Enforces permissions and records accesses.

Agents must use this facade — never JSONL files, KnowledgeStore internals, or a
future PostgreSQL client. Structured policy/tools remain authoritative; memory
only provides context, explanations, warnings, and confidence signals.

Multi-tenant scope (when organization_id is set on WorkflowState):
  short-term  → organization_id + workflow_id
  long-term   → organization_id + employee_id + workflow_type
  knowledge   → global corpus + that organization's documents only

Role-aware access is prepared via MemoryAccessContext / ROLE_MEMORY_SCOPE.
Full authentication and RBAC are Module 5+ work; empty user_role keeps current
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    # Recruitment-specialized agents
    "recruitment_planner": {"short_term": {"write"}},
    "job_research": {"short_term": {"write"}},
    "candidate_research": {"short_term": {"write"}},
    "candidate_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "candidate_scoring": {"short_term": {"write"}},
    "recruitment_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "recruitment_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "recruitment_validation": {"short_term": {"read"}},
    "recruitment_action": {"short_term": {"write"}},
    "recruitment_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # Onboarding-specialized agents
    "onboarding_planner": {"short_term": {"write"}},
    "employee_research": {"short_term": {"write"}},
    "document_verification": {"short_term": {"write"}},
    "onboarding_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "onboarding_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "onboarding_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "onboarding_validation": {"short_term": {"read"}},
    "onboarding_action": {"short_term": {"write"}},
    "onboarding_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # Attendance-specialized agents
    "attendance_planner": {"short_term": {"write"}},
    "attendance_research": {"short_term": {"write"}},
    "attendance_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "attendance_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "attendance_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "attendance_validation": {"short_term": {"read"}},
    "attendance_action": {"short_term": {"write"}},
    "attendance_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # Performance-specialized agents
    "performance_planner": {"short_term": {"write"}},
    "performance_research": {"short_term": {"write"}},
    "goal_analysis": {"short_term": {"write"}},
    "performance_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "performance_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "performance_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "performance_validation": {"short_term": {"read"}},
    "performance_action": {"short_term": {"write"}},
    "performance_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # Training-specialized agents
    "training_planner": {"short_term": {"write"}},
    "training_research": {"short_term": {"write"}},
    "skill_gap_analysis": {"short_term": {"write"}},
    "training_catalog_research": {"short_term": {"write"}},
    "training_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "training_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "training_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "training_validation": {"short_term": {"read"}},
    "training_action": {"short_term": {"write"}},
    "training_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # Offboarding-specialized agents
    "offboarding_planner": {"short_term": {"write"}},
    "offboarding_employee_research": {"short_term": {"write"}},
    "exit_details_research": {"short_term": {"write"}},
    "checklist_analysis": {"short_term": {"write"}},
    "offboarding_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "offboarding_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "offboarding_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "offboarding_validation": {"short_term": {"read"}},
    "offboarding_action": {"short_term": {"write"}},
    "offboarding_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
    # HR Services specialized agents
    "hr_services_planner": {"short_term": {"write"}},
    "request_classification": {"short_term": {"write"}},
    "employee_context": {"short_term": {"write"}},
    "service_research": {"short_term": {"write"}, "knowledge": {"read"}},
    "service_policy": {"short_term": {"write"}, "knowledge": {"read"}},
    "service_analysis": {
        "short_term": {"write"},
        "knowledge": {"read"},
    },
    "service_decision": {
        "short_term": {"read", "write"},
        "long_term": {"read"},
    },
    "service_validation": {"short_term": {"read"}},
    "service_action": {"short_term": {"write"}},
    "service_response": {
        "short_term": {"read"},
        "knowledge": {"read"},
        "long_term": {"write"},
    },
}

# Extension points for future role-aware retrieval. Not enforced as full RBAC yet.
ROLE_MEMORY_SCOPE: dict[str, dict[str, bool]] = {
    "employee": {"own_employee_only": True, "org_wide": False, "team_scope": False},
    "manager": {"own_employee_only": False, "org_wide": False, "team_scope": True},
    "hr_admin": {"own_employee_only": False, "org_wide": True, "team_scope": False},
    "system": {"own_employee_only": False, "org_wide": True, "team_scope": False},
}


@dataclass(frozen=True)
class MemoryAccessContext:
    """Caller identity/scope for memory operations. Filled from WorkflowState today."""

    organization_id: str = ""
    user_id: str = ""
    user_role: str = ""
    employee_id: str | None = None
    workflow_id: str = ""
    workflow_type: str | None = None


def _require(agent: str, layer: MemoryLayer, operation: str) -> None:
    allowed = AGENT_MEMORY_PERMISSIONS.get(agent, {}).get(layer, set())
    if operation not in allowed:
        raise MemoryPermissionError(
            f"Agent '{agent}' is not allowed to {operation} {layer} memory."
        )


def _employee_from_state(state: WorkflowState) -> str | None:
    leave_request = (state.get("metadata") or {}).get("leave_request") or {}
    employee_id = leave_request.get("employee_id") or (state.get("employee_data") or {}).get(
        "employee_id"
    )
    if employee_id:
        return str(employee_id)
    entities = state.get("entities") or {}
    entity_employee = entities.get("employee_id")
    return str(entity_employee) if entity_employee else None


def access_context_from_state(state: WorkflowState) -> MemoryAccessContext:
    """Build a MemoryAccessContext from WorkflowState multi-tenant fields."""

    return MemoryAccessContext(
        organization_id=str(state.get("organization_id") or ""),
        user_id=str(state.get("user_id") or ""),
        user_role=str(state.get("user_role") or ""),
        employee_id=_employee_from_state(state),
        workflow_id=str(state.get("workflow_id") or ""),
        workflow_type=state.get("workflow_type") or None,
    )


def _role_allows_employee_record(
    ctx: MemoryAccessContext,
    record_employee_id: str | None,
) -> bool:
    """Future RBAC hook. Empty role = no extra restriction (current leave behavior)."""

    role = (ctx.user_role or "").strip().lower()
    if not role:
        return True
    scope = ROLE_MEMORY_SCOPE.get(role)
    if scope is None:
        return True
    if scope.get("org_wide"):
        return True
    if scope.get("own_employee_only"):
        allowed = (ctx.employee_id or "").upper()
        if not allowed:
            return False
        return str(record_employee_id or "").upper() == allowed
    # manager/team_scope: keep org-scoped results for now; team membership comes later
    return True


def _filter_records_for_role(
    ctx: MemoryAccessContext,
    records: list[MemoryRecord],
) -> list[MemoryRecord]:
    return [
        record
        for record in records
        if _role_allows_employee_record(ctx, record.employee_id)
    ]


def _trace(
    *,
    ctx: MemoryAccessContext,
    agent: str,
    operation: str,
    layer: MemoryLayer,
    memory_ids: list[str],
    summary: str,
    influenced_decision: bool = False,
) -> dict[str, Any]:
    return memory_access_patch(
        agent=agent,
        operation=operation,  # type: ignore[arg-type]
        layer=layer,
        memory_ids=memory_ids,
        summary=summary,
        influenced_decision=influenced_decision,
        organization_id=ctx.organization_id,
        workflow_id=ctx.workflow_id,
        user_id=ctx.user_id,
    )


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
    ctx = access_context_from_state(state)
    record = get_short_term_store().append(
        workflow_id=ctx.workflow_id,
        content=content,
        kind=kind,
        agent=agent,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id or None,
        employee_id=employee_id or ctx.employee_id,
        workflow_type=workflow_type or ctx.workflow_type,
    )
    patch = _trace(
        ctx=ctx,
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
    ctx = access_context_from_state(state)
    records = get_short_term_store().list_for_workflow(
        ctx.workflow_id,
        organization_id=ctx.organization_id,
    )
    records = _filter_records_for_role(ctx, records)
    patch = _trace(
        ctx=ctx,
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
    filters: dict[str, Any] | None = None,
) -> tuple[list[KnowledgeHit], dict[str, Any]]:
    _require(agent, "knowledge", "read")
    ctx = access_context_from_state(state)
    hits = get_knowledge_store().search(
        query,
        organization_id=ctx.organization_id,
        workflow_type=workflow_type or ctx.workflow_type,
        doc_type=doc_type,
        filters=filters,
    )
    patch = _trace(
        ctx=ctx,
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
    ctx = access_context_from_state(state)
    target_employee = employee_id or ctx.employee_id
    if not target_employee:
        patch = _trace(
            ctx=ctx,
            agent=agent,
            operation="read",
            layer="long_term",
            memory_ids=[],
            summary="Skipped long-term recall; no employee id.",
        )
        return [], patch
    if not _role_allows_employee_record(ctx, target_employee):
        patch = _trace(
            ctx=ctx,
            agent=agent,
            operation="read",
            layer="long_term",
            memory_ids=[],
            summary="Long-term recall blocked by role scope.",
        )
        return [], patch
    records = get_long_term_store().query(
        employee_id=str(target_employee),
        organization_id=ctx.organization_id,
        workflow_type=workflow_type or ctx.workflow_type,
    )
    records = _filter_records_for_role(ctx, records)
    patch = _trace(
        ctx=ctx,
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
    ctx = access_context_from_state(state)
    # Organization scope always comes from WorkflowState, never from caller payload.
    merged = {
        **payload,
        "organization_id": ctx.organization_id,
        "workflow_id": payload.get("workflow_id") or ctx.workflow_id,
        "employee_id": payload.get("employee_id") or ctx.employee_id,
        "workflow_type": payload.get("workflow_type") or ctx.workflow_type,
    }
    if ctx.user_id:
        merged.setdefault("user_id", ctx.user_id)
    record = get_long_term_store().write(merged)
    patch = _trace(
        ctx=ctx,
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

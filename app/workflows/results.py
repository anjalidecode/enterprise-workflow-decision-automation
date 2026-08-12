"""Build audit snapshots and run metrics from WorkflowState traces."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.orchestration.state import WorkflowState
from app.workflows.contracts import WorkflowAuditSnapshot, WorkflowRunMetrics

# Tool-trace keys safe for dashboards / CLI. Never include raw payloads.
_SAFE_TOOL_KEYS = (
    "tool_name",
    "capability",
    "agent",
    "success",
    "attempts",
    "duration_ms",
    "error_code",
    "error_message",
    "organization_id",
    "workflow_id",
    "workflow_type",
    "side_effect",
)

_SAFE_MEMORY_KEYS = (
    "agent",
    "operation",
    "layer",
    "memory_ids",
    "summary",
    "influenced_decision",
    "organization_id",
    "workflow_id",
    "user_id",
    "timestamp",
)

_SAFE_DECISION_KEYS = (
    "outcome",
    "rationale",
    "executable",
    "confidence",
    "requires_human_approval",
    "entity_refs",
    "evidence",
    "blockers",
    "warnings",
    "influenced_by",
    "employee_id",
    "requested_days",
    "leave_type",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def _safe_tool_executions(state: WorkflowState) -> list[dict[str, Any]]:
    return [_pick(dict(item), _SAFE_TOOL_KEYS) for item in state.get("tool_executions") or []]


def _safe_memory_accesses(state: WorkflowState) -> list[dict[str, Any]]:
    return [_pick(dict(item), _SAFE_MEMORY_KEYS) for item in state.get("memory_accesses") or []]


def _safe_decision(state: WorkflowState) -> dict[str, Any]:
    decision = dict(state.get("decision") or {})
    return _pick(decision, _SAFE_DECISION_KEYS)


def _approval_checkpoint(state: WorkflowState) -> dict[str, Any] | None:
    metadata = state.get("metadata") or {}
    checkpoint = metadata.get("approval")
    if isinstance(checkpoint, dict) and checkpoint:
        return dict(checkpoint)
    if state.get("requires_human_approval") or state.get("status") == "awaiting_human_approval":
        return {
            "status": "awaiting",
            "workflow_id": state.get("workflow_id"),
            "organization_id": state.get("organization_id") or "",
            "workflow_type": state.get("workflow_type") or "",
            "reason": (state.get("decision") or {}).get("rationale") or "",
            "pending_actions": list(state.get("pending_actions") or []),
            "required_role": "manager",
        }
    return None


def build_audit_snapshot(
    state: WorkflowState,
    *,
    completed_at: str | None = None,
) -> WorkflowAuditSnapshot:
    decision = state.get("decision") or {}
    return WorkflowAuditSnapshot(
        workflow_id=str(state.get("workflow_id") or ""),
        organization_id=str(state.get("organization_id") or ""),
        workflow_type=str(state.get("workflow_type") or ""),
        started_at=str(state.get("created_at") or ""),
        completed_at=completed_at or _utc_now(),
        status=str(state.get("status") or ""),
        final_outcome=str(decision.get("outcome") or ""),
        agents_executed=[
            {
                "agent": item.get("agent"),
                "summary": item.get("summary"),
                "timestamp": item.get("timestamp"),
            }
            for item in state.get("agent_outputs") or []
        ],
        tool_executions=_safe_tool_executions(state),
        memory_accesses=_safe_memory_accesses(state),
        decision=_safe_decision(state),
        pending_actions=list(state.get("pending_actions") or []),
        completed_actions=list(state.get("completed_actions") or []),
        errors=list(state.get("errors") or []),
        approval_checkpoint=_approval_checkpoint(state),
    )


def build_run_metrics(
    state: WorkflowState,
    *,
    duration_ms: float,
) -> WorkflowRunMetrics:
    tools = list(state.get("tool_executions") or [])
    tool_count = len(tools)
    successes = sum(1 for item in tools if item.get("success"))
    retry_count = sum(max(int(item.get("attempts") or 1) - 1, 0) for item in tools)
    completed_actions = list(state.get("completed_actions") or [])
    action_successes = sum(1 for item in completed_actions if item.get("success"))
    decision = state.get("decision") or {}
    outcome = str(decision.get("outcome") or "")
    status = str(state.get("status") or "")

    return WorkflowRunMetrics(
        duration_ms=round(duration_ms, 3),
        agent_count=len(state.get("agent_outputs") or []),
        tool_count=tool_count,
        tool_success_rate=(successes / tool_count) if tool_count else 0.0,
        retry_count=retry_count,
        validation_failed=status == "validation_failed",
        human_approval_required=bool(
            state.get("requires_human_approval") or status == "awaiting_human_approval"
        ),
        decision_confidence=float(state.get("confidence") or decision.get("confidence") or 0.0),
        action_success_rate=(action_successes / len(completed_actions)) if completed_actions else 0.0,
        escalated=outcome == "escalate",
        workflow_type=str(state.get("workflow_type") or ""),
        organization_id=str(state.get("organization_id") or ""),
        status=status,
    )

"""Map WorkflowResult / domain audit+metrics into stable API schemas."""

from __future__ import annotations

from typing import Any

from app.api.schemas.workflows import (
    WorkflowAuditResponse,
    WorkflowDecisionResponse,
    WorkflowMetricsResponse,
    WorkflowRunResponse,
    WorkflowSummary,
)
from app.workflows.contracts import WorkflowResult


def _approval_status(state: dict[str, Any], audit_checkpoint: dict[str, Any] | None) -> str | None:
    metadata = state.get("metadata") or {}
    approval = metadata.get("approval")
    if isinstance(approval, dict) and approval.get("status"):
        return str(approval["status"])
    if audit_checkpoint and audit_checkpoint.get("status"):
        return str(audit_checkpoint["status"])
    if state.get("requires_human_approval") or state.get("status") == "awaiting_human_approval":
        return "awaiting"
    return None


def _decision_response(state: dict[str, Any]) -> WorkflowDecisionResponse | None:
    decision = state.get("decision") or {}
    if not decision:
        return None
    return WorkflowDecisionResponse(
        outcome=str(decision.get("outcome") or ""),
        rationale=str(decision.get("rationale") or ""),
        confidence=float(
            state.get("confidence")
            if state.get("confidence") is not None
            else decision.get("confidence") or 0.0
        ),
        requires_human_approval=bool(
            decision.get("requires_human_approval") or state.get("requires_human_approval")
        ),
        executable=bool(decision.get("executable")),
        entity_refs=dict(decision.get("entity_refs") or {}),
        evidence=list(decision.get("evidence") or []),
        blockers=list(decision.get("blockers") or []),
        warnings=list(decision.get("warnings") or []),
    )


def to_audit_response(result: WorkflowResult) -> WorkflowAuditResponse:
    audit = result.audit
    return WorkflowAuditResponse(
        workflow_id=audit.workflow_id,
        organization_id=audit.organization_id,
        workflow_type=audit.workflow_type,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        status=audit.status,
        final_outcome=audit.final_outcome,
        agents=list(audit.agents_executed),
        tool_executions=list(audit.tool_executions),
        memory_accesses=list(audit.memory_accesses),
        decision=dict(audit.decision),
        actions=list(audit.completed_actions),
        pending_actions=list(audit.pending_actions),
        errors=list(audit.errors),
        approval_checkpoint=audit.approval_checkpoint,
    )


def to_metrics_response(result: WorkflowResult) -> WorkflowMetricsResponse:
    metrics = result.metrics
    state = result.state or {}
    action_count = len(state.get("completed_actions") or []) + len(
        state.get("pending_actions") or []
    )
    status = str(metrics.status or state.get("status") or "")
    # Terminal completed runs count as successful for API consumers; validation_failed
    # and non-completed statuses do not. Soft trace messages in state.errors do not
    # override a completed decision path.
    success = status == "completed" and not metrics.validation_failed
    return WorkflowMetricsResponse(
        duration_ms=metrics.duration_ms,
        agent_count=metrics.agent_count,
        tool_count=metrics.tool_count,
        tool_success_rate=metrics.tool_success_rate,
        retry_count=metrics.retry_count,
        action_count=action_count,
        action_success_rate=metrics.action_success_rate,
        validation_failed=metrics.validation_failed,
        human_approval_required=metrics.human_approval_required,
        decision_confidence=metrics.decision_confidence,
        escalated=metrics.escalated,
        workflow_type=metrics.workflow_type,
        organization_id=metrics.organization_id,
        status=status,
        success=success,
    )


def to_run_response(result: WorkflowResult, *, request_id: str = "") -> WorkflowRunResponse:
    state = result.state or {}
    audit = to_audit_response(result)
    return WorkflowRunResponse(
        workflow_id=str(state.get("workflow_id") or ""),
        workflow_type=str(state.get("workflow_type") or ""),
        status=str(state.get("status") or ""),
        current_stage=str(state.get("current_stage") or ""),
        organization_id=str(state.get("organization_id") or ""),
        decision=_decision_response(state),
        response=str(state.get("final_response") or ""),
        actions=list(state.get("completed_actions") or []),
        pending_actions=list(state.get("pending_actions") or []),
        errors=list(state.get("errors") or []),
        approval_status=_approval_status(state, audit.approval_checkpoint),
        audit=audit,
        metrics=to_metrics_response(result),
        router_status=result.router.status if result.router else None,
        request_id=request_id or str(state.get("request_id") or ""),
    )


def to_summary(result: WorkflowResult) -> WorkflowSummary:
    state = result.state or {}
    decision = state.get("decision") or {}
    metadata = state.get("metadata") or {}
    approval = metadata.get("approval") if isinstance(metadata.get("approval"), dict) else None
    approval_status = None
    if approval and approval.get("status"):
        approval_status = str(approval["status"])
    elif state.get("status") == "awaiting_human_approval":
        approval_status = "awaiting"
    return WorkflowSummary(
        workflow_id=str(state.get("workflow_id") or ""),
        workflow_type=str(state.get("workflow_type") or ""),
        status=str(state.get("status") or ""),
        organization_id=str(state.get("organization_id") or ""),
        created_at=str(state.get("created_at") or ""),
        outcome=str(decision.get("outcome") or ""),
        approval_status=approval_status,
    )

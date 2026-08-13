"""Persistence service — maps WorkflowResult to PostgreSQL in one transaction.

Does not replace WorkflowState / LangGraph. Stores application/platform records
and an optional approval checkpoint snapshot for engine.resume after restart.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError, PersistenceConflictError
from app.database.models.workflow import WorkflowRun
from app.database.repositories.approval import ApprovalRepository
from app.database.repositories.audit import AuditRepository
from app.database.repositories.decision import DecisionRepository
from app.database.repositories.metrics import MetricsRepository
from app.database.repositories.organization import OrganizationRepository
from app.database.repositories.workflow import WorkflowRepository
from app.workflows.contracts import (
    RouterResult,
    WorkflowAuditSnapshot,
    WorkflowResult,
    WorkflowRunMetrics,
)

logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _snapshot_from_result(result: WorkflowResult) -> dict[str, Any]:
    """Compact JSON payload sufficient to rebuild WorkflowResult for the API."""

    return {
        "state": dict(result.state or {}),
        "audit": result.audit.model_dump(),
        "metrics": result.metrics.model_dump(),
        "router": result.router.model_dump() if result.router else None,
        "spec_version": result.spec_version,
    }


def workflow_result_from_run(run: WorkflowRun) -> WorkflowResult | None:
    snap = run.result_snapshot or {}
    if not snap.get("state"):
        return None
    audit_data = snap.get("audit") or {}
    metrics_data = snap.get("metrics") or {}
    router_data = snap.get("router")
    return WorkflowResult(
        state=dict(snap.get("state") or {}),
        audit=WorkflowAuditSnapshot.model_validate(audit_data),
        metrics=WorkflowRunMetrics.model_validate(metrics_data),
        router=RouterResult.model_validate(router_data) if router_data else None,
        spec_version=str(snap.get("spec_version") or ""),
    )


class PersistenceService:
    """Transactional writer/reader for platform workflow records."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.organizations = OrganizationRepository(session)
        self.workflows = WorkflowRepository(session)
        self.decisions = DecisionRepository(session)
        self.approvals = ApprovalRepository(session)
        self.audits = AuditRepository(session)
        self.metrics = MetricsRepository(session)

    def ensure_organization(self, organization_id: str, *, name: str | None = None) -> None:
        if not organization_id:
            return
        self.organizations.create(
            organization_id=organization_id,
            name=name or organization_id,
        )

    def persist_workflow_result(self, result: WorkflowResult) -> WorkflowRun:
        """Persist run + decision + audit + metrics (+ approval) atomically."""

        state = result.state or {}
        workflow_id = str(state.get("workflow_id") or "").strip()
        organization_id = str(state.get("organization_id") or "").strip()
        if not workflow_id or not organization_id:
            raise PersistenceConflictError(
                "Cannot persist workflow result without workflow_id and organization_id."
            )

        self.ensure_organization(organization_id)
        decision = dict(state.get("decision") or {})
        status = str(state.get("status") or "")
        started_at = _parse_iso(str(state.get("created_at") or ""))
        completed_at = _parse_iso(str(result.audit.completed_at or ""))
        requires_approval = bool(
            state.get("requires_human_approval") or status == "awaiting_human_approval"
        )

        try:
            run = self.workflows.upsert_run(
                workflow_id=workflow_id,
                organization_id=organization_id,
                workflow_type=str(state.get("workflow_type") or ""),
                user_id=str(state.get("user_id") or ""),
                status=status,
                current_stage=str(state.get("current_stage") or ""),
                started_at=started_at,
                completed_at=completed_at,
                outcome=str(decision.get("outcome") or ""),
                requires_human_approval=requires_approval,
                result_snapshot=_snapshot_from_result(result),
                final_response=str(state.get("final_response") or ""),
            )

            self.decisions.upsert(
                workflow_id=workflow_id,
                organization_id=organization_id,
                outcome=str(decision.get("outcome") or ""),
                rationale=str(decision.get("rationale") or ""),
                confidence=float(
                    state.get("confidence")
                    if state.get("confidence") is not None
                    else decision.get("confidence") or 0.0
                ),
                executable=bool(decision.get("executable")),
                requires_human_approval=bool(
                    decision.get("requires_human_approval") or requires_approval
                ),
                entity_refs=dict(decision.get("entity_refs") or {}),
                evidence=list(decision.get("evidence") or []),
                blockers=list(decision.get("blockers") or []),
                warnings=list(decision.get("warnings") or []),
                influenced_by=list(decision.get("influenced_by") or []),
                decided_at=datetime.now(timezone.utc),
            )

            audit = result.audit
            self.audits.upsert(
                workflow_id=workflow_id,
                organization_id=organization_id,
                workflow_type=audit.workflow_type,
                status=audit.status,
                started_at=audit.started_at,
                completed_at=audit.completed_at,
                final_outcome=audit.final_outcome,
                agents_executed=list(audit.agents_executed),
                tool_executions=list(audit.tool_executions),
                memory_accesses=list(audit.memory_accesses),
                decision_summary=dict(audit.decision),
                actions=list(audit.completed_actions),
                pending_actions=list(audit.pending_actions),
                errors=list(audit.errors),
                approval_checkpoint=audit.approval_checkpoint,
            )

            metrics = result.metrics
            action_count = len(state.get("completed_actions") or []) + len(
                state.get("pending_actions") or []
            )
            success = status == "completed" and not metrics.validation_failed
            self.metrics.upsert(
                workflow_id=workflow_id,
                organization_id=organization_id,
                duration_ms=float(metrics.duration_ms),
                agent_count=int(metrics.agent_count),
                tool_count=int(metrics.tool_count),
                action_count=action_count,
                tool_success_rate=float(metrics.tool_success_rate),
                action_success_rate=float(metrics.action_success_rate),
                retry_count=int(metrics.retry_count),
                validation_failed=bool(metrics.validation_failed),
                human_approval_required=bool(metrics.human_approval_required),
                decision_confidence=float(metrics.decision_confidence),
                escalated=bool(metrics.escalated),
                success=success,
                workflow_type=str(metrics.workflow_type or state.get("workflow_type") or ""),
                status=status,
            )

            if requires_approval or status == "awaiting_human_approval":
                metadata = state.get("metadata") or {}
                approval_meta = metadata.get("approval") if isinstance(metadata, dict) else {}
                if not isinstance(approval_meta, dict):
                    approval_meta = {}
                self.approvals.upsert_awaiting(
                    workflow_id=workflow_id,
                    organization_id=organization_id,
                    requested_by=str(state.get("user_id") or ""),
                    reason=str(
                        approval_meta.get("reason")
                        or decision.get("rationale")
                        or ""
                    ),
                    required_role=str(approval_meta.get("required_role") or "manager"),
                    pending_actions=list(
                        approval_meta.get("pending_actions")
                        or state.get("pending_actions")
                        or []
                    ),
                    checkpoint_state=dict(state),
                    requested_at=_parse_iso(str(approval_meta.get("created_at") or ""))
                    or datetime.now(timezone.utc),
                )
            else:
                approval_meta = (state.get("metadata") or {}).get("approval") or {}
                if isinstance(approval_meta, dict) and approval_meta.get("status") in {
                    "approved",
                    "rejected",
                }:
                    self.approvals.mark_decided(
                        workflow_id=workflow_id,
                        organization_id=organization_id,
                        decision=str(approval_meta.get("status")),
                        decided_by=str(approval_meta.get("decided_by") or ""),
                        reason=str(approval_meta.get("comment") or approval_meta.get("reason") or ""),
                        decided_at=_parse_iso(str(approval_meta.get("decided_at") or "")),
                    )

            self._session.flush()
            return run
        except PersistenceConflictError:
            raise
        except PermissionError as exc:
            raise PersistenceConflictError(str(exc)) from exc
        except Exception as exc:
            logger.exception("failed to persist workflow result")
            raise DatabaseUnavailableError(
                "Failed to persist workflow result."
            ) from exc

    def get_result(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> WorkflowResult | None:
        run = self.workflows.get_by_workflow_id(
            workflow_id, organization_id=organization_id
        )
        if run is None:
            return None
        return workflow_result_from_run(run)

    def list_results(
        self,
        *,
        organization_id: str,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WorkflowResult], int]:
        # Load all matching for ownership filter at API layer, then slice there
        # when needed. Here we still honor limit/offset for raw org queries.
        runs, total = self.workflows.list_for_organization(
            organization_id=organization_id,
            workflow_type=workflow_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        results: list[WorkflowResult] = []
        for run in runs:
            rebuilt = workflow_result_from_run(run)
            if rebuilt is not None:
                results.append(rebuilt)
        return results, total

    def load_approval_checkpoint(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> dict[str, Any] | None:
        record = self.approvals.get_by_workflow_id(
            workflow_id, organization_id=organization_id
        )
        if record is None or record.decision != "awaiting":
            return None
        if not record.checkpoint_state:
            return None
        return dict(record.checkpoint_state)

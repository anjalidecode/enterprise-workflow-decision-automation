"""Audit repository — organization-scoped."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.audit import AuditRecord


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_workflow_id(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> AuditRecord | None:
        stmt = select(AuditRecord).where(
            AuditRecord.workflow_id == workflow_id,
            AuditRecord.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def upsert(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        workflow_type: str,
        status: str,
        started_at: str,
        completed_at: str,
        final_outcome: str,
        agents_executed: list[Any],
        tool_executions: list[Any],
        memory_accesses: list[Any],
        decision_summary: dict[str, Any],
        actions: list[Any],
        pending_actions: list[Any],
        errors: list[Any],
        approval_checkpoint: dict[str, Any] | None,
    ) -> AuditRecord:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            record = AuditRecord(
                workflow_id=workflow_id,
                organization_id=organization_id,
                workflow_type=workflow_type,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                final_outcome=final_outcome,
                agents_executed=agents_executed,
                tool_executions=tool_executions,
                memory_accesses=memory_accesses,
                decision_summary=decision_summary,
                actions=actions,
                pending_actions=pending_actions,
                errors=errors,
                approval_checkpoint=approval_checkpoint,
            )
            self._session.add(record)
            self._session.flush()
            return record

        existing.workflow_type = workflow_type
        existing.status = status
        existing.started_at = started_at
        existing.completed_at = completed_at
        existing.final_outcome = final_outcome
        existing.agents_executed = agents_executed
        existing.tool_executions = tool_executions
        existing.memory_accesses = memory_accesses
        existing.decision_summary = decision_summary
        existing.actions = actions
        existing.pending_actions = pending_actions
        existing.errors = errors
        existing.approval_checkpoint = approval_checkpoint
        self._session.flush()
        return existing

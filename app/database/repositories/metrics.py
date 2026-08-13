"""Metrics repository — organization-scoped."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.metrics import MetricsRecord


class MetricsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_workflow_id(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> MetricsRecord | None:
        stmt = select(MetricsRecord).where(
            MetricsRecord.workflow_id == workflow_id,
            MetricsRecord.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def upsert(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        duration_ms: float,
        agent_count: int,
        tool_count: int,
        action_count: int,
        tool_success_rate: float,
        action_success_rate: float,
        retry_count: int,
        validation_failed: bool,
        human_approval_required: bool,
        decision_confidence: float,
        escalated: bool,
        success: bool,
        workflow_type: str,
        status: str,
    ) -> MetricsRecord:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            record = MetricsRecord(
                workflow_id=workflow_id,
                organization_id=organization_id,
                duration_ms=duration_ms,
                agent_count=agent_count,
                tool_count=tool_count,
                action_count=action_count,
                tool_success_rate=tool_success_rate,
                action_success_rate=action_success_rate,
                retry_count=retry_count,
                validation_failed=validation_failed,
                human_approval_required=human_approval_required,
                decision_confidence=decision_confidence,
                escalated=escalated,
                success=success,
                workflow_type=workflow_type,
                status=status,
            )
            self._session.add(record)
            self._session.flush()
            return record

        existing.duration_ms = duration_ms
        existing.agent_count = agent_count
        existing.tool_count = tool_count
        existing.action_count = action_count
        existing.tool_success_rate = tool_success_rate
        existing.action_success_rate = action_success_rate
        existing.retry_count = retry_count
        existing.validation_failed = validation_failed
        existing.human_approval_required = human_approval_required
        existing.decision_confidence = decision_confidence
        existing.escalated = escalated
        existing.success = success
        existing.workflow_type = workflow_type
        existing.status = status
        self._session.flush()
        return existing

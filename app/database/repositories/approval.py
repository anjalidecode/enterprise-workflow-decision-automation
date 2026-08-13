"""Approval repository — organization-scoped."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.database.models.approval import ApprovalRecord


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_workflow_id(
        self,
        workflow_id: str,
        *,
        organization_id: str,
    ) -> ApprovalRecord | None:
        stmt = select(ApprovalRecord).where(
            ApprovalRecord.workflow_id == workflow_id,
            ApprovalRecord.organization_id == organization_id,
        )
        return self._session.scalars(stmt).first()

    def upsert_awaiting(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        requested_by: str,
        reason: str,
        required_role: str,
        pending_actions: list[Any],
        checkpoint_state: dict[str, Any],
        requested_at: datetime | None = None,
    ) -> ApprovalRecord:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            record = ApprovalRecord(
                workflow_id=workflow_id,
                organization_id=organization_id,
                requested_by=requested_by,
                reason=reason,
                required_role=required_role,
                pending_actions=pending_actions,
                checkpoint_state=checkpoint_state,
                decision="awaiting",
                requested_at=requested_at or utc_now(),
            )
            self._session.add(record)
            self._session.flush()
            return record

        existing.requested_by = requested_by
        existing.reason = reason
        existing.required_role = required_role
        existing.pending_actions = pending_actions
        existing.checkpoint_state = checkpoint_state
        existing.decision = "awaiting"
        existing.decided_at = None
        existing.decided_by = None
        if requested_at:
            existing.requested_at = requested_at
        self._session.flush()
        return existing

    def mark_decided(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        decision: str,
        decided_by: str,
        reason: str = "",
        decided_at: datetime | None = None,
    ) -> ApprovalRecord | None:
        existing = self.get_by_workflow_id(workflow_id, organization_id=organization_id)
        if existing is None:
            return None
        existing.decision = decision
        existing.decided_by = decided_by
        existing.decided_at = decided_at or utc_now()
        if reason:
            existing.reason = reason
        existing.checkpoint_state = None
        self._session.flush()
        return existing

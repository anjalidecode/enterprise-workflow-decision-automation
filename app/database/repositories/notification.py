"""Repository for notification event records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.database.models.notification import NotificationEventRecord


class NotificationEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency(
        self,
        *,
        organization_id: str,
        idempotency_key: str,
    ) -> NotificationEventRecord | None:
        stmt = select(NotificationEventRecord).where(
            NotificationEventRecord.organization_id == organization_id,
            NotificationEventRecord.idempotency_key == idempotency_key,
        )
        return self._session.scalars(stmt).first()

    def create(
        self,
        *,
        event_id: str,
        organization_id: str,
        event_type: str,
        idempotency_key: str,
        recipient_user_id: str = "",
        recipient_email: str = "",
        workflow_run_id: str = "",
        provider: str = "",
        status: str = "pending",
        audit_meta: dict[str, Any] | None = None,
    ) -> NotificationEventRecord:
        record = NotificationEventRecord(
            event_id=event_id,
            organization_id=organization_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            recipient_user_id=recipient_user_id or None,
            recipient_email=recipient_email,
            workflow_run_id=workflow_run_id or None,
            provider=provider,
            status=status,
            attempt_count=0,
            audit_meta=dict(audit_meta or {}),
        )
        self._session.add(record)
        self._session.flush()
        return record

    def mark_success(
        self,
        record: NotificationEventRecord,
        *,
        provider: str,
        status: str,
        audit_meta: dict[str, Any] | None = None,
    ) -> NotificationEventRecord:
        record.provider = provider
        record.status = status
        record.attempt_count = int(record.attempt_count or 0) + 1
        record.sent_at = utc_now()
        record.failed_at = None
        record.error_code = None
        record.error_message = None
        if audit_meta:
            meta = dict(record.audit_meta or {})
            meta.update(audit_meta)
            record.audit_meta = meta
        self._session.flush()
        return record

    def mark_failure(
        self,
        record: NotificationEventRecord,
        *,
        provider: str,
        error_code: str,
        error_message: str,
    ) -> NotificationEventRecord:
        record.provider = provider
        record.status = "failed"
        record.attempt_count = int(record.attempt_count or 0) + 1
        record.failed_at = utc_now()
        record.error_code = (error_code or "")[:64]
        record.error_message = (error_message or "")[:500]
        self._session.flush()
        return record

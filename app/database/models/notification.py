"""Persisted notification delivery / idempotency records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class NotificationEventRecord(TimestampMixin, Base):
    """Durable notification attempt. Never store secrets or raw invite tokens."""

    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_notification_events_org_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

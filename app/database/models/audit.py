"""Persisted audit snapshot for a workflow run."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utc_now


class AuditRecord(TimestampMixin, Base):
    __tablename__ = "audits"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_audits_workflow_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    started_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    completed_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    final_outcome: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    agents_executed: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tool_executions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    memory_accesses: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    decision_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    pending_actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    approval_checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    workflow_run = relationship("WorkflowRun", back_populates="audit")

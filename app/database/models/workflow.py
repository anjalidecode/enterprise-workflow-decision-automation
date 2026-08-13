"""Workflow run summary — persistent application record, not live LangGraph state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utc_now


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_workflow_runs_workflow_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Sanitized API-oriented snapshot for retrieval (not LangGraph live state).
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    final_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    organization = relationship("Organization", back_populates="workflow_runs")
    decision = relationship(
        "DecisionRecord",
        back_populates="workflow_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    approval = relationship(
        "ApprovalRecord",
        back_populates="workflow_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    audit = relationship(
        "AuditRecord",
        back_populates="workflow_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    metrics = relationship(
        "MetricsRecord",
        back_populates="workflow_run",
        uselist=False,
        cascade="all, delete-orphan",
    )

"""Persisted run metrics."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class MetricsRecord(TimestampMixin, Base):
    __tablename__ = "metrics"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_metrics_workflow_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    action_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decision_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    workflow_run = relationship("WorkflowRun", back_populates="metrics")

"""Persisted human-approval checkpoint (business state, not LangGraph checkpoint)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, utc_now


class ApprovalRecord(TimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_approvals_workflow_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="awaiting")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_role: Mapped[str] = mapped_column(String(32), nullable=False, default="manager")
    pending_actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # WorkflowState snapshot required by WorkflowEngine.resume after process restart.
    # This is approval/business resume state — not full LangGraph graph checkpointing.
    checkpoint_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    workflow_run = relationship("WorkflowRun", back_populates="approval")

"""notification events table

Revision ID: a1b2c3d4e5f6
Revises: 7c8e4a21b9d0
Create Date: 2026-08-17 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7c8e4a21b9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_user_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "audit_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_events")),
        sa.UniqueConstraint("event_id", name=op.f("uq_notification_events_event_id")),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_notification_events_org_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_notification_events_event_id"),
        "notification_events",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_organization_id"),
        "notification_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_event_type"),
        "notification_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_events_workflow_run_id"),
        "notification_events",
        ["workflow_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_events_workflow_run_id"), table_name="notification_events")
    op.drop_index(op.f("ix_notification_events_event_type"), table_name="notification_events")
    op.drop_index(op.f("ix_notification_events_organization_id"), table_name="notification_events")
    op.drop_index(op.f("ix_notification_events_event_id"), table_name="notification_events")
    op.drop_table("notification_events")

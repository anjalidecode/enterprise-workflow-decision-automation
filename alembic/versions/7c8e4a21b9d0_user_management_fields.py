"""user management fields

Revision ID: 7c8e4a21b9d0
Revises: 465751d099fc
Create Date: 2026-08-15 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c8e4a21b9d0"
down_revision: Union[str, Sequence[str], None] = "465751d099fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("users", sa.Column("invite_token_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE users SET status = 'inactive' WHERE is_active = false AND status = 'active'"
    )


def downgrade() -> None:
    op.drop_column("users", "invite_expires_at")
    op.drop_column("users", "invite_token_hash")
    op.drop_column("users", "status")
    op.drop_column("users", "full_name")

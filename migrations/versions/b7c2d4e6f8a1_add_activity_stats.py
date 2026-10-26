"""add activity and batch counters

Revision ID: b7c2d4e6f8a1
Revises: 8c4f6a1d2b90
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b7c2d4e6f8a1"
down_revision: str | None = "8c4f6a1d2b90"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "activity_hourly",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("hour_start", sa.Text(), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "hour_start"),
    )
    op.create_index(
        "ix_activity_hourly_start",
        "activity_hourly",
        ["hour_start"],
        unique=False,
    )
    op.create_table(
        "activity_daily",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("day", sa.Text(), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "day"),
    )
    op.create_index(
        "ix_activity_daily_day",
        "activity_daily",
        ["day"],
        unique=False,
    )
    op.create_table(
        "batch_counters",
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inbound", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("late_replies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("batch_id"),
    )


def downgrade() -> None:
    op.drop_table("batch_counters")
    op.drop_index("ix_activity_daily_day", table_name="activity_daily")
    op.drop_table("activity_daily")
    op.drop_index("ix_activity_hourly_start", table_name="activity_hourly")
    op.drop_table("activity_hourly")

"""add dispatch quota and failure queue

Revision ID: 8c4f6a1d2b90
Revises: 7b3e5d9c1a24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "8c4f6a1d2b90"
down_revision: str | None = "7b3e5d9c1a24"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "quota_buckets",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("day", sa.Text(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "day"),
    )
    op.create_table(
        "failed_queue",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_failed_queue_failed_at", "failed_queue", ["failed_at"])


def downgrade() -> None:
    op.drop_index("ix_failed_queue_failed_at", table_name="failed_queue")
    op.drop_table("failed_queue")
    op.drop_table("quota_buckets")

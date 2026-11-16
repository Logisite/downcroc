"""add send attempt thread backfill status

Revision ID: 4f8dbcf4f792
Revises: g1b2c3d4e5f6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "4f8dbcf4f792"
down_revision: str | None = "g1b2c3d4e5f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("send_attempts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("provider_thread_status", sa.Text(), nullable=True)
        )
        batch_op.add_column(sa.Column("thread_first_miss_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thread_missing_at", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("send_attempts", schema=None) as batch_op:
        batch_op.drop_column("thread_missing_at")
        batch_op.drop_column("thread_first_miss_at")
        batch_op.drop_column("provider_thread_status")

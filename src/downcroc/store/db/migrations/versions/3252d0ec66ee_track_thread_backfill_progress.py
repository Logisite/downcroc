"""track thread backfill progress

Revision ID: 3252d0ec66ee
Revises: 4f8dbcf4f792
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "3252d0ec66ee"
down_revision: str | None = "4f8dbcf4f792"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("send_attempts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("thread_last_checked_at", sa.Text(), nullable=True)
        )
        batch_op.add_column(sa.Column("thread_next_check_at", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "thread_check_count",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("thread_last_result", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thread_last_scope", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thread_last_error", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_send_attempts_thread_due",
            ["account_id", "thread_next_check_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("send_attempts", schema=None) as batch_op:
        batch_op.drop_index("ix_send_attempts_thread_due")
        batch_op.drop_column("thread_last_error")
        batch_op.drop_column("thread_last_scope")
        batch_op.drop_column("thread_last_result")
        batch_op.drop_column("thread_check_count")
        batch_op.drop_column("thread_next_check_at")
        batch_op.drop_column("thread_last_checked_at")

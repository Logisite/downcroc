"""add sender policy and send attempts

Revision ID: f3a1b8c7d2e4
Revises: a4d8e2f6c9b3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1b8c7d2e4"
down_revision: str | None = "a4d8e2f6c9b3"
branch_labels: str | None = None
depends_on: str | None = None

_POLICY = (
    "(sender_policy = 'pinned' AND account_id IS NOT NULL) "
    "OR (sender_policy = 'auto' AND account_id IS NULL)"
)


def upgrade() -> None:
    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "sender_policy",
                sa.Text(),
                nullable=False,
                server_default="pinned",
            )
        )
        batch.alter_column("account_id", existing_type=sa.Text(), nullable=True)
        batch.create_check_constraint("ck_jobs_sender_policy", _POLICY)
    with op.batch_alter_table("failed_queue", recreate="always") as batch:
        batch.alter_column("account_id", existing_type=sa.Text(), nullable=True)
    op.create_table(
        "send_attempts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=True),
        sa.Column("transport", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_send_attempts_job_started",
        "send_attempts",
        ["job_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_send_attempts_job_started", table_name="send_attempts")
    op.drop_table("send_attempts")
    with op.batch_alter_table("failed_queue", recreate="always") as batch:
        batch.alter_column("account_id", existing_type=sa.Text(), nullable=False)
    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.drop_constraint("ck_jobs_sender_policy", type_="check")
        batch.drop_column("sender_policy")
        batch.alter_column("account_id", existing_type=sa.Text(), nullable=False)

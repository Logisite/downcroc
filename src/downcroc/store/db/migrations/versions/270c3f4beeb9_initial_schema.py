"""initial schema

Revision ID: 270c3f4beeb9
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "270c3f4beeb9"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("credential_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_verified_at", sa.Text(), nullable=True),
        sa.Column("daily_allowance", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("window_end", sa.Integer(), nullable=False),
        sa.Column("jitter_min", sa.Integer(), nullable=False),
        sa.Column("jitter_max", sa.Integer(), nullable=False),
        sa.Column("max_in_flight", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id", "address", name="uq_accounts_provider_address"
        ),
    )
    op.create_table(
        "events",
        sa.Column("seq", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("ts", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("seq"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "account_state",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("watcher_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_uid", sa.Integer(), nullable=False),
        sa.Column("last_sync_at", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("recipient_name", sa.Text(), nullable=True),
        sa.Column("vars_json", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_ref", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.Text(), nullable=True),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_jobs_account_created", ["account_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_jobs_batch_state", ["batch_id", "state"], unique=False
        )
        batch_op.create_index(
            "ix_jobs_state_next", ["state", "next_attempt_at"], unique=False
        )

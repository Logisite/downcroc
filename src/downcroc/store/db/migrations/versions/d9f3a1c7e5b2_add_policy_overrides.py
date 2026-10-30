"""add nullable policy overrides and quota reservations

Revision ID: d9f3a1c7e5b2
Revises: c5b8e1f4a7d2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d9f3a1c7e5b2"
down_revision: str | None = "c5b8e1f4a7d2"
branch_labels: str | None = None
depends_on: str | None = None

POLICY_COLUMNS = (
    ("daily_allowance", sa.Integer()),
    ("window_start", sa.Integer()),
    ("window_end", sa.Integer()),
    ("jitter_min", sa.Integer()),
    ("jitter_max", sa.Integer()),
    ("max_in_flight", sa.Integer()),
    ("enabled", sa.Boolean()),
)


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        for name, kind in POLICY_COLUMNS:
            batch.alter_column(name, existing_type=kind, nullable=True)
    op.execute(
        "UPDATE accounts SET daily_allowance = NULL, window_start = NULL, "
        "window_end = NULL, jitter_min = NULL, jitter_max = NULL, "
        "max_in_flight = NULL, enabled = NULL"
    )
    op.create_table(
        "policy_overrides",
        sa.Column("scope", sa.Text(), primary_key=True),
        sa.Column("daily_allowance", sa.Integer(), nullable=True),
        sa.Column("window_start", sa.Integer(), nullable=True),
        sa.Column("window_end", sa.Integer(), nullable=True),
        sa.Column("jitter_min", sa.Integer(), nullable=True),
        sa.Column("jitter_max", sa.Integer(), nullable=True),
        sa.Column("max_in_flight", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.add_column(
        "quota_buckets",
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("quota_buckets", "reserved")
    op.drop_table("policy_overrides")
    op.execute(
        "UPDATE accounts SET daily_allowance = 200, window_start = 0, "
        "window_end = 24, jitter_min = 30, jitter_max = 90, "
        "max_in_flight = 2, enabled = 1"
    )
    with op.batch_alter_table("accounts") as batch:
        for name, kind in POLICY_COLUMNS:
            batch.alter_column(name, existing_type=kind, nullable=False)

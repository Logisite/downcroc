"""add attempts

Revision ID: 9c1e4b2a7f30
Revises: 270c3f4beeb9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "9c1e4b2a7f30"
down_revision: str | None = "270c3f4beeb9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "attempts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("authorization_url", sa.Text(), nullable=False),
        sa.Column("state_token", sa.Text(), nullable=False),
        sa.Column("callback_port", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attempts_account_created",
        "attempts",
        ["account_id", "created_at"],
        unique=False,
    )

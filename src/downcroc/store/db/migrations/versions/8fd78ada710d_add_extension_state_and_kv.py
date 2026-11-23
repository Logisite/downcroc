"""add extension state and kv

Revision ID: 8fd78ada710d
Revises: 43e936cccfe9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "8fd78ada710d"
down_revision: str | None = "43e936cccfe9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "extension_kv",
        sa.Column("extension_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("extension_id", "key"),
    )
    op.create_table(
        "extension_state",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("restarts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("extension_state")
    op.drop_table("extension_kv")

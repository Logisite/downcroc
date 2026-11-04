"""record the installation's first initialization timestamp

Revision ID: c9f4b2a7e610
Revises: 00ec13530758
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c9f4b2a7e610"
down_revision: str | None = "00ec13530758"
branch_labels: str | None = None
depends_on: str | None = None

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"


def upgrade() -> None:
    op.add_column(
        "runtime_state",
        sa.Column("initialized_at", sa.Text(), nullable=True),
    )
    op.execute(
        f"""
        INSERT INTO runtime_state (id, updated_at, initialized_at)
        SELECT 1, {_NOW},
               COALESCE((SELECT MIN(created_at) FROM accounts), {_NOW})
        WHERE NOT EXISTS (SELECT 1 FROM runtime_state)
        """
    )
    op.execute(
        f"""
        UPDATE runtime_state
        SET initialized_at = COALESCE(
            (SELECT MIN(created_at) FROM accounts),
            {_NOW}
        )
        WHERE initialized_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("runtime_state", "initialized_at")

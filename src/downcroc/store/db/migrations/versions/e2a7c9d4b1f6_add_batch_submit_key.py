"""add batch submit key

Revision ID: e2a7c9d4b1f6
Revises: b7c2d4e6f8a1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e2a7c9d4b1f6"
down_revision: str | None = "b7c2d4e6f8a1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("submit_key", sa.Text(), nullable=True))
    op.create_index(
        "ux_batches_source_submit_key",
        "batches",
        ["source_hash", "submit_key"],
        unique=True,
        sqlite_where=sa.text("submit_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_batches_source_submit_key", table_name="batches")
    op.drop_column("batches", "submit_key")

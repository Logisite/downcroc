"""add extension approvals

Revision ID: 96073f83071c
Revises: 8fd78ada710d
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "96073f83071c"
down_revision: str | None = "8fd78ada710d"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "extension_approvals",
        sa.Column("extension_id", sa.Text(), nullable=False),
        sa.Column("manifest_digest", sa.Text(), nullable=False),
        sa.Column("capability_digest", sa.Text(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("extension_id"),
    )


def downgrade() -> None:
    op.drop_table("extension_approvals")

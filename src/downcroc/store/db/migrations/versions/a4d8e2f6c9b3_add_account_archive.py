"""add account archive and job batch selection index

Revision ID: a4d8e2f6c9b3
Revises: e2a7c9d4b1f6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a4d8e2f6c9b3"
down_revision: str | None = "e2a7c9d4b1f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("archived_at", sa.Text(), nullable=True))
    op.create_index(
        "ix_jobs_batch_created",
        "jobs",
        ["batch_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_batch_created", table_name="jobs")
    op.drop_column("accounts", "archived_at")

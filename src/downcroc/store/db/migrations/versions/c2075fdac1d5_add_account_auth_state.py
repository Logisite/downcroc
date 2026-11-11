"""add account auth state

Revision ID: c2075fdac1d5
Revises: c9f4b2a7e610
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c2075fdac1d5"
down_revision: str | None = "c9f4b2a7e610"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("auth_checked_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("auth_status", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("auth_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("auth_action", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_column("auth_action")
        batch_op.drop_column("auth_error")
        batch_op.drop_column("auth_status")
        batch_op.drop_column("auth_checked_at")

"""add provider thread id to send attempts

Revision ID: g1b2c3d4e5f6
Revises: 22173c4abcd7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "g1b2c3d4e5f6"
down_revision: str | None = "22173c4abcd7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("send_attempts") as batch:
        batch.add_column(sa.Column("provider_thread_id", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("send_attempts") as batch:
        batch.drop_column("provider_thread_id")

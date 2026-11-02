"""add inbound source cursors and provider message ids

Revision ID: a4e8c2d6f1b9
Revises: d9f3a1c7e5b2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a4e8c2d6f1b9"
down_revision: str | None = "d9f3a1c7e5b2"
branch_labels: str | None = None
depends_on: str | None = None

STATE_COLUMNS = (
    ("source_override", sa.Text()),
    ("inbound_source", sa.Text()),
    ("history_id", sa.Text()),
    ("cursor_source", sa.Text()),
    ("last_sweep_at", sa.Text()),
    ("last_source_switch_at", sa.Text()),
)


def upgrade() -> None:
    with op.batch_alter_table("account_state") as batch:
        for name, kind in STATE_COLUMNS:
            batch.add_column(sa.Column(name, kind, nullable=True))
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("provider_id", sa.Text(), nullable=True))
    op.create_index(
        "uq_messages_provider",
        "messages",
        ["account_id", "provider_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_messages_provider", table_name="messages")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("provider_id")
    with op.batch_alter_table("account_state") as batch:
        for name, _ in reversed(STATE_COLUMNS):
            batch.drop_column(name)

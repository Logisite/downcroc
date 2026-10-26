"""add inbound storage

Revision ID: 5d9a7c1e3b42
Revises: 9c1e4b2a7f30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "5d9a7c1e3b42"
down_revision: str | None = "9c1e4b2a7f30"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "account_state",
        sa.Column(
            "uidvalidity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "threads",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("root_message_id", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("reply_count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.Text(), nullable=False),
        sa.Column("last_seen", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("folder", sa.Text(), nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("uidvalidity", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=True),
        sa.Column("in_reply_to", sa.Text(), nullable=True),
        sa.Column("references_json", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("from_address", sa.Text(), nullable=False),
        sa.Column("from_name", sa.Text(), nullable=False),
        sa.Column("to_json", sa.Text(), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("is_dsn", sa.Boolean(), nullable=False),
        sa.Column("reply_state", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=True),
        sa.Column("job_id", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_truncated", sa.Boolean(), nullable=False),
        sa.Column("ingested_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "folder",
            "uidvalidity",
            "uid",
            name="uq_messages_server_identity",
        ),
        sa.UniqueConstraint(
            "account_id",
            "message_id",
            name="uq_messages_account_header",
        ),
    )
    op.create_index(
        "ix_messages_thread_date",
        "messages",
        ["thread_id", "date"],
        unique=False,
    )
    op.create_index("ix_messages_job", "messages", ["job_id"], unique=False)
    op.create_index("ix_messages_message_id", "messages", ["message_id"], unique=False)
    op.create_index(
        "ix_messages_account_date",
        "messages",
        ["account_id", "date"],
        unique=False,
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("inline", sa.Boolean(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "thread_links",
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("relation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", "thread_id"),
    )

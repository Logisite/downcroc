"""add followup declarations

Revision ID: 22173c4abcd7
Revises: c2075fdac1d5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "22173c4abcd7"
down_revision: str | None = "c2075fdac1d5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "batch_followup_declarations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("after_days", sa.Integer(), nullable=False),
        sa.Column("when", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("require_approval", sa.Integer(), nullable=False),
        sa.Column("overrides_json", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_followup_declarations_batch_state",
        "batch_followup_declarations",
        ["batch_id", "state"],
    )
    op.create_index(
        "ix_followup_declarations_state_days",
        "batch_followup_declarations",
        ["state", "after_days"],
    )
    op.create_index(
        "ux_followup_declarations_batch_step",
        "batch_followup_declarations",
        ["batch_id", "step_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_followup_declarations_batch_step",
        table_name="batch_followup_declarations",
    )
    op.drop_index(
        "ix_followup_declarations_state_days",
        table_name="batch_followup_declarations",
    )
    op.drop_index(
        "ix_followup_declarations_batch_state",
        table_name="batch_followup_declarations",
    )
    op.drop_table("batch_followup_declarations")

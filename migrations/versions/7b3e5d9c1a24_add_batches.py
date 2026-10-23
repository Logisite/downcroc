"""add batches and job source provenance

Revision ID: 7b3e5d9c1a24
Revises: 5d9a7c1e3b42
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "7b3e5d9c1a24"
down_revision: str | None = "5d9a7c1e3b42"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("parent_batch_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=True),
        sa.Column("campaign_key", sa.Text(), nullable=True),
        sa.Column("producer_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("template_ref", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Text(), nullable=True),
        sa.Column("routing_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("approval", sa.Text(), nullable=False, server_default="review"),
        sa.Column("options_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("sample_job_id", sa.Text(), nullable=True),
        sa.Column("samples_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ignored_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batches_state_created", "batches", ["state", "created_at"])
    op.create_index("ix_batches_campaign_key", "batches", ["campaign_key"])
    op.create_index("ix_batches_parent", "batches", ["parent_batch_id"])

    op.add_column(
        "jobs",
        sa.Column("source_kind", sa.Text(), nullable=False, server_default="manual"),
    )
    op.add_column("jobs", sa.Column("source_key", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("source_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("jobs", sa.Column("step_key", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("parent_job_id", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("thread_root_job_id", sa.Text(), nullable=True))
    op.create_index("ix_jobs_thread_root", "jobs", ["thread_root_job_id"])
    op.create_index(
        "ux_jobs_batch_source_key",
        "jobs",
        ["batch_id", "source_key"],
        unique=True,
        sqlite_where=sa.text("source_key IS NOT NULL"),
    )
    op.create_index(
        "ux_jobs_parent_step",
        "jobs",
        ["parent_job_id", "step_key"],
        unique=True,
        sqlite_where=sa.text("step_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_jobs_parent_step", table_name="jobs")
    op.drop_index("ux_jobs_batch_source_key", table_name="jobs")
    op.drop_index("ix_jobs_thread_root", table_name="jobs")
    op.drop_column("jobs", "thread_root_job_id")
    op.drop_column("jobs", "parent_job_id")
    op.drop_column("jobs", "step_key")
    op.drop_column("jobs", "source_index")
    op.drop_column("jobs", "source_key")
    op.drop_column("jobs", "source_kind")

    op.drop_index("ix_batches_parent", table_name="batches")
    op.drop_index("ix_batches_campaign_key", table_name="batches")
    op.drop_index("ix_batches_state_created", table_name="batches")
    op.drop_table("batches")

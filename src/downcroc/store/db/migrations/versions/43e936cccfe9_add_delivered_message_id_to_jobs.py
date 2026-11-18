"""add delivered message id to jobs

Revision ID: 43e936cccfe9
Revises: 3252d0ec66ee
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "43e936cccfe9"
down_revision: str | None = "3252d0ec66ee"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("delivered_message_id", sa.Text(), nullable=True))

    # SMTP preserves our minted Message-ID, so for jobs whose final accepted
    # send went over SMTP the delivered id is the minted id. API jobs are left
    # NULL: their real id is a provider value that needs a credential to recover
    # and is filled at send time, by the background backfill, or on demand.
    op.execute(
        """
        UPDATE jobs
        SET delivered_message_id = message_id
        WHERE delivered_message_id IS NULL
          AND (
            SELECT a.transport
            FROM send_attempts a
            WHERE a.job_id = jobs.id
              AND a.outcome = 'sent'
              AND a.accepted = 1
            ORDER BY a.started_at DESC, a.id DESC
            LIMIT 1
          ) = 'smtp'
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("delivered_message_id")

"""add transport bindings and oauth clients

Revision ID: c5b8e1f4a7d2
Revises: f3a1b8c7d2e4
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision: str = "c5b8e1f4a7d2"
down_revision: str | None = "f3a1b8c7d2e4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oauth_clients_provider", "oauth_clients", ["provider_id"])
    op.create_table(
        "account_transports",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("credential_ref", sa.Text(), nullable=True),
        sa.Column("oauth_client_id", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rate_per_min", sa.Integer(), nullable=True),
        sa.Column("health", sa.Text(), nullable=False, server_default="ready"),
        sa.Column("cooldown_until", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["oauth_client_id"], ["oauth_clients.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "kind",
            "provider_id",
            name="uq_account_transports_account_kind_provider",
        ),
    )
    op.create_index(
        "ix_account_transports_account", "account_transports", ["account_id"]
    )
    op.add_column("send_attempts", sa.Column("binding_id", sa.Text(), nullable=True))
    _backfill_smtp_bindings()


def _backfill_smtp_bindings() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, provider_id, credential_key, created_at FROM accounts")
    ).all()
    for account_id, provider_id, credential_key, created_at in rows:
        bind.execute(
            sa.text(
                "INSERT INTO account_transports "
                "(id, account_id, provider_id, kind, credential_ref, enabled, "
                "priority, max_concurrency, health, created_at, updated_at) "
                "VALUES (:id, :account_id, :provider_id, 'smtp', :credential_ref, "
                "1, 0, 1, 'ready', :created_at, :created_at)"
            ),
            {
                "id": f"trn_{secrets.token_hex(8)}",
                "account_id": account_id,
                "provider_id": provider_id,
                "credential_ref": credential_key,
                "created_at": created_at,
            },
        )


def downgrade() -> None:
    op.drop_column("send_attempts", "binding_id")
    op.drop_index("ix_account_transports_account", table_name="account_transports")
    op.drop_table("account_transports")
    op.drop_index("ix_oauth_clients_provider", table_name="oauth_clients")
    op.drop_table("oauth_clients")

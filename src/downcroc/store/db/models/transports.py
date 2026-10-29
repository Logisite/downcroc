from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class AccountTransportRow(Base):
    __tablename__ = "account_transports"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "kind",
            "provider_id",
            name="uq_account_transports_account_kind_provider",
        ),
        Index("ix_account_transports_account", "account_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(Text)
    oauth_client_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("oauth_clients.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rate_per_min: Mapped[int | None] = mapped_column(Integer)
    health: Mapped[str] = mapped_column(Text, nullable=False, default="ready")
    cooldown_until: Mapped[str | None] = mapped_column(Text)
    last_error_code: Mapped[str | None] = mapped_column(Text)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class OAuthClientRow(Base):
    __tablename__ = "oauth_clients"
    __table_args__ = (Index("ix_oauth_clients_provider", "provider_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str | None] = mapped_column(Text)
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

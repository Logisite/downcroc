from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class AccountRow(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("provider_id", "address", name="uq_accounts_provider_address"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    credential_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_verified_at: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[str | None] = mapped_column(Text)
    daily_allowance: Mapped[int | None] = mapped_column(Integer)
    window_start: Mapped[int | None] = mapped_column(Integer)
    window_end: Mapped[int | None] = mapped_column(Integer)
    jitter_min: Mapped[int | None] = mapped_column(Integer)
    jitter_max: Mapped[int | None] = mapped_column(Integer)
    max_in_flight: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool | None] = mapped_column(Boolean)
    paused_at: Mapped[str | None] = mapped_column(Text)
    paused_reason: Mapped[str | None] = mapped_column(Text)


class AccountStateRow(Base):
    __tablename__ = "account_state"

    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    watcher_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_uid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uidvalidity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_at: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    source_override: Mapped[str | None] = mapped_column(Text)
    inbound_source: Mapped[str | None] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(Text)
    cursor_source: Mapped[str | None] = mapped_column(Text)
    last_sweep_at: Mapped[str | None] = mapped_column(Text)
    last_source_switch_at: Mapped[str | None] = mapped_column(Text)

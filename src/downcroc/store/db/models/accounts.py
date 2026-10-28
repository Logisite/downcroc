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
    daily_allowance: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[int] = mapped_column(Integer, nullable=False)
    window_end: Mapped[int] = mapped_column(Integer, nullable=False)
    jitter_min: Mapped[int] = mapped_column(Integer, nullable=False)
    jitter_max: Mapped[int] = mapped_column(Integer, nullable=False)
    max_in_flight: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)


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

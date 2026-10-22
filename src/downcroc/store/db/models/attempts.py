from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class AttemptRow(Base):
    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_account_created", "account_id", "created_at"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    authorization_url: Mapped[str] = mapped_column(Text, nullable=False)
    state_token: Mapped[str] = mapped_column(Text, nullable=False)
    callback_port: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

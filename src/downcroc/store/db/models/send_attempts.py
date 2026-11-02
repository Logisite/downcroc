from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class SendAttemptRow(Base):
    __tablename__ = "send_attempts"
    __table_args__ = (
        Index("ix_send_attempts_job_started", "job_id", "started_at"),
        Index(
            "ix_attempts_quota_reserved",
            "quota_state",
            sqlite_where=text("quota_state = 'reserved'"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(
        Text, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="SET NULL")
    )
    binding_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("account_transports.id", ondelete="SET NULL")
    )
    transport: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    quota_day: Mapped[str | None] = mapped_column(Text)
    quota_state: Mapped[str | None] = mapped_column(Text)

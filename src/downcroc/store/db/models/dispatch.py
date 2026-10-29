from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class QuotaBucketRow(Base):
    __tablename__ = "quota_buckets"

    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[str] = mapped_column(Text, primary_key=True)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FailedJobRow(Base):
    __tablename__ = "failed_queue"
    __table_args__ = (Index("ix_failed_queue_failed_at", "failed_at"),)

    job_id: Mapped[str] = mapped_column(
        Text, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str | None] = mapped_column(Text)
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_at: Mapped[str] = mapped_column(Text, nullable=False)

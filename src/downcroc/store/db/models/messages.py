from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "folder",
            "uidvalidity",
            "uid",
            name="uq_messages_server_identity",
        ),
        UniqueConstraint(
            "account_id",
            "message_id",
            name="uq_messages_account_header",
        ),
        Index("ix_messages_thread_date", "thread_id", "date"),
        Index("ix_messages_job", "job_id"),
        Index("ix_messages_message_id", "message_id"),
        Index("ix_messages_account_date", "account_id", "date"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        Text, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    folder: Mapped[str] = mapped_column(Text, nullable=False)
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    uidvalidity: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text)
    in_reply_to: Mapped[str | None] = mapped_column(Text)
    references_json: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    from_address: Mapped[str] = mapped_column(Text, nullable=False)
    from_name: Mapped[str] = mapped_column(Text, nullable=False)
    to_json: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    is_dsn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reply_state: Mapped[str] = mapped_column(Text, nullable=False, default="none")
    thread_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("threads.id", ondelete="SET NULL")
    )
    job_id: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    body_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingested_at: Mapped[str] = mapped_column(Text, nullable=False)


class AttachmentRow(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        Text, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(Text, nullable=False)
    inline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_id: Mapped[str | None] = mapped_column(Text)


class ThreadRow(Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    root_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen: Mapped[str] = mapped_column(Text, nullable=False)


class ThreadLinkRow(Base):
    __tablename__ = "thread_links"

    message_id: Mapped[str] = mapped_column(
        Text, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    thread_id: Mapped[str] = mapped_column(
        Text, ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)

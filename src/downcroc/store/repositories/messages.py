from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import (
    AttachmentNotFound,
    MessageNotFound,
    ThreadNotFound,
)
from downcroc.domain.messages import (
    Attachment,
    Message,
    MessageSummary,
    Thread,
)
from downcroc.store.db.models.accounts import AccountRow
from downcroc.store.db.models.messages import (
    AttachmentRow,
    MessageRow,
    ThreadRow,
)
from downcroc.store.repositories.message_inbound import (
    InboundMixin,
    IngestResult,
)

__all__ = ["IngestResult", "MessageRepo", "PrunableMail"]


@dataclass(frozen=True)
class PrunableMail:
    message_id: str
    thread_id: str | None
    bytes: int
    attachment_paths: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class _MailAccumulator:
    thread_id: str | None
    bytes: int
    attachment_paths: list[str] = field(default_factory=list)


def _summary(row: MessageRow, attachment_count: int) -> MessageSummary:
    return MessageSummary(
        id=row.id,
        account_id=row.account_id,
        folder=row.folder,
        uid=row.uid,
        message_id=row.message_id,
        subject=row.subject,
        from_address=row.from_address,
        from_name=row.from_name,
        date=row.date,
        size=row.size,
        is_dsn=row.is_dsn,
        reply_state=row.reply_state,
        thread_id=row.thread_id,
        job_id=row.job_id,
        ingested_at=row.ingested_at,
        attachment_count=attachment_count,
    )


def _thread(row: ThreadRow) -> Thread:
    return Thread(
        id=row.id,
        root_message_id=row.root_message_id,
        subject=row.subject,
        batch_id=row.batch_id,
        message_count=row.message_count,
        reply_count=row.reply_count,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
    )


def _attachment(row: AttachmentRow) -> Attachment:
    return Attachment(
        id=row.id,
        message_id=row.message_id,
        filename=row.filename,
        content_type=row.content_type,
        size=row.size,
        path=row.path,
        hash=row.hash,
        inline=row.inline,
        content_id=row.content_id,
    )


class MessageRepo(InboundMixin):
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def list_messages(
        self,
        *,
        account_id: str | None = None,
        folder: str | None = None,
        thread_id: str | None = None,
        reply_state: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageSummary]:
        count = (
            select(func.count())
            .select_from(AttachmentRow)
            .where(AttachmentRow.message_id == MessageRow.id)
            .scalar_subquery()
        )
        query = select(MessageRow, count.label("attachment_count"))
        if account_id is not None:
            query = query.where(MessageRow.account_id == account_id)
        if folder is not None:
            query = query.where(MessageRow.folder == folder)
        if thread_id is not None:
            query = query.where(MessageRow.thread_id == thread_id)
        if reply_state is not None:
            query = query.where(MessageRow.reply_state == reply_state)
        if since is not None:
            query = query.where(MessageRow.date >= since)
        if until is not None:
            query = query.where(MessageRow.date <= until)
        query = query.order_by(MessageRow.date.desc(), MessageRow.id.desc())
        query = query.limit(limit).offset(offset)
        with self._sessions() as session:
            rows = session.execute(query).all()
            return [_summary(row, count) for row, count in rows]

    def count_messages(
        self,
        *,
        account_id: str | None = None,
        folder: str | None = None,
        thread_id: str | None = None,
        reply_state: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(MessageRow)
        if account_id is not None:
            query = query.where(MessageRow.account_id == account_id)
        if folder is not None:
            query = query.where(MessageRow.folder == folder)
        if thread_id is not None:
            query = query.where(MessageRow.thread_id == thread_id)
        if reply_state is not None:
            query = query.where(MessageRow.reply_state == reply_state)
        if since is not None:
            query = query.where(MessageRow.date >= since)
        if until is not None:
            query = query.where(MessageRow.date <= until)
        with self._sessions() as session:
            return int(session.scalar(query) or 0)

    def get_message(self, message_id: str) -> Message:
        with self._sessions() as session:
            row = session.get(MessageRow, message_id)
            if row is None:
                raise MessageNotFound(f"no message {message_id}")
            attachments = session.execute(
                select(AttachmentRow)
                .where(AttachmentRow.message_id == message_id)
                .order_by(AttachmentRow.id)
            ).scalars()
            return Message(
                id=row.id,
                account_id=row.account_id,
                folder=row.folder,
                uid=row.uid,
                uidvalidity=row.uidvalidity,
                message_id=row.message_id,
                in_reply_to=row.in_reply_to,
                references=tuple(json.loads(row.references_json)),
                subject=row.subject,
                from_address=row.from_address,
                from_name=row.from_name,
                to=tuple(json.loads(row.to_json)),
                date=row.date,
                size=row.size,
                is_dsn=row.is_dsn,
                reply_state=row.reply_state,
                thread_id=row.thread_id,
                job_id=row.job_id,
                body_text=row.body_text,
                body_html=row.body_html,
                body_truncated=row.body_truncated,
                ingested_at=row.ingested_at,
                attachments=tuple(_attachment(item) for item in attachments),
            )

    def get_attachment(self, message_id: str, attachment_id: str) -> Attachment:
        with self._sessions() as session:
            row = session.get(AttachmentRow, attachment_id)
            if row is None or row.message_id != message_id:
                raise AttachmentNotFound(f"no attachment {attachment_id}")
            return _attachment(row)

    def list_threads(
        self,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Thread]:
        query = select(ThreadRow)
        if account_id is not None:
            query = query.where(
                ThreadRow.id.in_(
                    select(MessageRow.thread_id).where(
                        MessageRow.account_id == account_id,
                        MessageRow.thread_id.is_not(None),
                    )
                )
            )
        if batch_id is not None:
            query = query.where(ThreadRow.batch_id == batch_id)
        query = query.order_by(ThreadRow.last_seen.desc(), ThreadRow.id.desc())
        query = query.limit(limit).offset(offset)
        with self._sessions() as session:
            return [_thread(row) for row in session.execute(query).scalars()]

    def count_threads(
        self,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(ThreadRow)
        if account_id is not None:
            query = query.where(
                ThreadRow.id.in_(
                    select(MessageRow.thread_id).where(
                        MessageRow.account_id == account_id,
                        MessageRow.thread_id.is_not(None),
                    )
                )
            )
        if batch_id is not None:
            query = query.where(ThreadRow.batch_id == batch_id)
        with self._sessions() as session:
            return int(session.scalar(query) or 0)

    def get_thread(self, thread_id: str) -> tuple[Thread, list[MessageSummary]]:
        count = (
            select(func.count())
            .select_from(AttachmentRow)
            .where(AttachmentRow.message_id == MessageRow.id)
            .scalar_subquery()
        )
        with self._sessions() as session:
            row = session.get(ThreadRow, thread_id)
            if row is None:
                raise ThreadNotFound(f"no thread {thread_id}")
            messages = session.execute(
                select(MessageRow, count.label("attachment_count"))
                .where(MessageRow.thread_id == thread_id)
                .order_by(MessageRow.date, MessageRow.id)
            ).all()
            return _thread(row), [_summary(item, total) for item, total in messages]

    def activity_rows(self) -> list[tuple[str, str, bool, str, str | None]]:
        with self._sessions() as session:
            rows = session.execute(
                select(
                    MessageRow.account_id,
                    MessageRow.ingested_at,
                    MessageRow.is_dsn,
                    MessageRow.reply_state,
                    MessageRow.job_id,
                )
            )
            return [(row[0], row[1], bool(row[2]), row[3], row[4]) for row in rows]

    def prunable_mail(self, cutoff: str) -> list[PrunableMail]:
        found: dict[str, _MailAccumulator] = {}
        with self._sessions() as session:
            rows = session.execute(
                select(MessageRow, AttachmentRow)
                .outerjoin(AttachmentRow, AttachmentRow.message_id == MessageRow.id)
                .where(MessageRow.ingested_at < cutoff)
            ).all()
            for message, attachment in rows:
                item = found.setdefault(
                    message.id,
                    _MailAccumulator(
                        thread_id=message.thread_id,
                        bytes=len(message.body_text or "")
                        + len(message.body_html or ""),
                    ),
                )
                if attachment is not None:
                    item.bytes += attachment.size
                    item.attachment_paths.append(attachment.path)
        return [
            PrunableMail(
                message_id=message_id,
                thread_id=item.thread_id,
                bytes=item.bytes,
                attachment_paths=tuple(item.attachment_paths),
            )
            for message_id, item in found.items()
        ]

    def prunable_self(self, account_id: str | None = None) -> list[PrunableMail]:
        """Inbox rows that are copies of mail sent by one of our accounts."""
        accounts = select(AccountRow.address)
        query = (
            select(MessageRow, AttachmentRow)
            .outerjoin(AttachmentRow, AttachmentRow.message_id == MessageRow.id)
            .where(
                MessageRow.folder == "INBOX",
                MessageRow.from_address.in_(accounts),
                MessageRow.job_id.is_(None),
                MessageRow.reply_state == "none",
                MessageRow.is_dsn.is_(False),
            )
        )
        if account_id is not None:
            query = query.where(MessageRow.account_id == account_id)
        found: dict[str, _MailAccumulator] = {}
        with self._sessions() as session:
            for message, attachment in session.execute(query).all():
                item = found.setdefault(
                    message.id,
                    _MailAccumulator(
                        thread_id=message.thread_id,
                        bytes=len(message.body_text or "")
                        + len(message.body_html or ""),
                    ),
                )
                if attachment is not None:
                    item.bytes += attachment.size
                    item.attachment_paths.append(attachment.path)
        return [
            PrunableMail(
                message_id=message_id,
                thread_id=item.thread_id,
                bytes=item.bytes,
                attachment_paths=tuple(item.attachment_paths),
            )
            for message_id, item in found.items()
        ]

    def delete_mail(self, message_ids: list[str]) -> int:
        if not message_ids:
            return 0
        with self._sessions.begin() as session:
            thread_ids = set(
                session.scalars(
                    select(MessageRow.thread_id)
                    .where(MessageRow.id.in_(message_ids))
                    .where(MessageRow.thread_id.is_not(None))
                )
            )
            result = session.execute(
                delete(MessageRow).where(MessageRow.id.in_(message_ids))
            )
            for thread_id in thread_ids:
                thread = session.get(ThreadRow, thread_id)
                if thread is None:
                    continue
                remaining = session.execute(
                    select(MessageRow.is_dsn, MessageRow.reply_state).where(
                        MessageRow.thread_id == thread_id
                    )
                ).all()
                if not remaining:
                    session.delete(thread)
                    continue
                thread.message_count = len(remaining)
                thread.reply_count = sum(
                    1 for _, state in remaining if state == "confirmed"
                )
            return int(result.rowcount or 0)

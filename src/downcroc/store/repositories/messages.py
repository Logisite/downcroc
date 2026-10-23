from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.errors import (
    AttachmentNotFound,
    MessageNotFound,
    ThreadNotFound,
)
from downcroc.domain.messages import (
    Attachment,
    IncomingMessage,
    Message,
    MessageSummary,
    PreparedAttachment,
    Thread,
    normalize_subject,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.store.db.models.accounts import AccountStateRow
from downcroc.store.db.models.messages import (
    AttachmentRow,
    MessageRow,
    ThreadLinkRow,
    ThreadRow,
)


@dataclass(frozen=True)
class IngestResult:
    message_id: str
    thread_id: str
    created: bool
    attachments: tuple[PreparedAttachment, ...] = ()


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


class MessageRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def find_existing(
        self,
        account_id: str,
        folder: str,
        uidvalidity: int,
        uid: int,
        message_id: str | None,
    ) -> IngestResult | None:
        with self._sessions() as session:
            clauses = [
                (MessageRow.account_id == account_id)
                & (MessageRow.folder == folder)
                & (MessageRow.uidvalidity == uidvalidity)
                & (MessageRow.uid == uid)
            ]
            if message_id is not None:
                clauses.append(
                    (MessageRow.account_id == account_id)
                    & (MessageRow.message_id == message_id)
                )
            row = session.execute(
                select(MessageRow).where(or_(*clauses)).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return IngestResult(
                message_id=row.id,
                thread_id=row.thread_id or "",
                created=False,
            )

    def advance_cursor(
        self,
        account_id: str,
        uidvalidity: int,
        uid: int,
        synced_at: str,
    ) -> None:
        with self._sessions.begin() as session:
            state = session.get(AccountStateRow, account_id)
            if state is None:
                state = AccountStateRow(account_id=account_id)
                session.add(state)
            if state.uidvalidity != uidvalidity:
                state.uidvalidity = uidvalidity
                state.last_uid = uid
            else:
                state.last_uid = max(state.last_uid, uid)
            state.last_sync_at = synced_at
            state.last_error = None
            state.consecutive_failures = 0

    def ingest(
        self,
        account_id: str,
        folder: str,
        incoming: IncomingMessage,
        attachments: tuple[PreparedAttachment, ...],
        message_id: str | None = None,
    ) -> IngestResult:
        message_id = message_id or new_id("msg")
        ingested_at = utc_now()
        with self._sessions.begin() as session:
            thread, relation = self._thread_for(
                session, account_id, incoming, message_id
            )
            row = MessageRow(
                id=message_id,
                account_id=account_id,
                folder=folder,
                uid=incoming.uid,
                uidvalidity=incoming.uidvalidity,
                message_id=incoming.message_id,
                in_reply_to=incoming.in_reply_to,
                references_json=json.dumps(list(incoming.references)),
                subject=incoming.subject,
                from_address=incoming.from_address,
                from_name=incoming.from_name,
                to_json=json.dumps(list(incoming.to)),
                date=incoming.date,
                size=incoming.size,
                is_dsn=False,
                reply_state="none",
                thread_id=thread.id,
                job_id=None,
                body_text=incoming.body_text,
                body_html=incoming.body_html,
                body_truncated=incoming.body_truncated,
                ingested_at=ingested_at,
            )
            session.add(row)
            session.flush()
            for prepared in attachments:
                session.add(
                    AttachmentRow(
                        id=prepared.id,
                        message_id=message_id,
                        filename=prepared.filename,
                        content_type=prepared.content_type,
                        size=prepared.size,
                        path=prepared.path,
                        hash=prepared.hash,
                        inline=prepared.inline,
                        content_id=prepared.content_id,
                    )
                )
            session.add(
                ThreadLinkRow(
                    message_id=message_id,
                    thread_id=thread.id,
                    relation=relation,
                )
            )
            thread.message_count += 1
            thread.last_seen = max(thread.last_seen, incoming.date)
            state = session.get(AccountStateRow, account_id)
            if state is None:
                state = AccountStateRow(account_id=account_id)
                session.add(state)
            if state.uidvalidity != incoming.uidvalidity:
                state.uidvalidity = incoming.uidvalidity
                state.last_uid = incoming.uid
            else:
                state.last_uid = max(state.last_uid, incoming.uid)
            state.last_sync_at = ingested_at
            state.last_error = None
            state.consecutive_failures = 0
        return IngestResult(
            message_id=message_id,
            thread_id=thread.id,
            created=True,
            attachments=attachments,
        )

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

    def _thread_for(
        self,
        session: Session,
        account_id: str,
        incoming: IncomingMessage,
        fallback_root: str,
    ) -> tuple[ThreadRow, str]:
        candidates = [
            value
            for value in (incoming.in_reply_to, *reversed(incoming.references))
            if value
        ]
        ordered = list(dict.fromkeys(candidates))
        if ordered:
            rows = session.execute(
                select(MessageRow.message_id, MessageRow.thread_id).where(
                    MessageRow.account_id == account_id,
                    MessageRow.message_id.in_(ordered),
                    MessageRow.thread_id.is_not(None),
                )
            ).all()
            found = {message_id: thread_id for message_id, thread_id in rows}
            for candidate in ordered:
                thread_id = found.get(candidate)
                if thread_id is None:
                    continue
                thread = session.get(ThreadRow, thread_id)
                if thread is not None:
                    return thread, "reply"
        thread = ThreadRow(
            id=new_id("thr"),
            root_message_id=incoming.message_id or fallback_root,
            subject=normalize_subject(incoming.subject) or "(no subject)",
            batch_id=None,
            message_count=0,
            reply_count=0,
            first_seen=incoming.date,
            last_seen=incoming.date,
        )
        session.add(thread)
        session.flush()
        return thread, "root"

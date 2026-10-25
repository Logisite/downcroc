from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.messages import IncomingMessage, PreparedAttachment
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.store.db.models.accounts import AccountStateRow
from downcroc.store.db.models.jobs import JobRow
from downcroc.store.db.models.messages import AttachmentRow, MessageRow, ThreadLinkRow
from downcroc.store.repositories import replies, thread_signals
from downcroc.store.repositories.replies import BatchTotals
from downcroc.store.repositories.thread_signals import ThreadSignals


@dataclass(frozen=True)
class IngestResult:
    message_id: str
    thread_id: str
    created: bool
    attachments: tuple[PreparedAttachment, ...] = ()
    is_dsn: bool = False
    reply_state: str = "none"
    job_id: str | None = None
    root_job_id: str | None = None
    batch_id: str | None = None
    relation: str = "root"
    method: str = "new"
    confirmed: bool = False
    suppression_added: bool = False
    suppression_account_id: str | None = None
    dsn_status: str | None = None
    dsn_code: str | None = None
    dsn_recipient: str | None = None
    unattributed_reason: str | None = None


class InboundMixin:
    _sessions: sessionmaker[Session]

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
            _advance_cursor(session, account_id, uidvalidity, uid, synced_at)

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
            attribution = replies.resolve(session, account_id, incoming, message_id)
            thread = attribution.thread
            suppressed = False
            suppression_account = None
            if attribution.reply_state == "confirmed" and attribution.job_id:
                job = session.get(JobRow, attribution.job_id)
                if job is not None:
                    suppression_account = job.account_id
                    suppressed = not replies.suppressed_address(
                        session, job.account_id, incoming.from_address
                    )
            session.add(
                MessageRow(
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
                    is_dsn=incoming.is_dsn,
                    reply_state=attribution.reply_state,
                    thread_id=thread.id,
                    job_id=attribution.job_id,
                    body_text=incoming.body_text,
                    body_html=incoming.body_html,
                    body_truncated=incoming.body_truncated,
                    ingested_at=ingested_at,
                )
            )
            session.flush()
            for prepared in attachments:
                session.add(_attachment(message_id, prepared))
            session.add(
                ThreadLinkRow(
                    message_id=message_id,
                    thread_id=thread.id,
                    relation=attribution.relation,
                )
            )
            thread.message_count += 1
            thread.last_seen = max(thread.last_seen, incoming.date)
            if attribution.reply_state == "confirmed":
                thread.reply_count += 1
            _advance_cursor(
                session,
                account_id,
                incoming.uidvalidity,
                incoming.uid,
                ingested_at,
            )
        return IngestResult(
            message_id=message_id,
            thread_id=thread.id,
            created=True,
            attachments=attachments,
            is_dsn=incoming.is_dsn,
            reply_state=attribution.reply_state,
            job_id=attribution.job_id,
            root_job_id=attribution.root_job_id,
            batch_id=attribution.batch_id,
            relation=attribution.relation,
            method=attribution.method,
            confirmed=attribution.reply_state == "confirmed",
            suppression_added=suppressed,
            suppression_account_id=suppression_account,
            dsn_status=incoming.dsn_status,
            dsn_code=incoming.dsn_code,
            dsn_recipient=incoming.dsn_recipient,
            unattributed_reason=attribution.unattributed_reason,
        )

    def batch_totals(self, batch_id: str, window_days: int) -> BatchTotals:
        with self._sessions() as session:
            return replies.batch_totals(session, batch_id, window_days)

    def suppressed_addresses(self, account_id: str) -> set[str]:
        with self._sessions() as session:
            return replies.suppressed_addresses(session, account_id)

    def thread_signals(self, root_message_ids: list[str]) -> ThreadSignals:
        with self._sessions() as session:
            return thread_signals.thread_signals(session, root_message_ids)

    def thread_signals_by_root(
        self, root_message_ids: list[str]
    ) -> dict[str, ThreadSignals]:
        with self._sessions() as session:
            return thread_signals.thread_signals_by_root(session, root_message_ids)


def _attachment(message_id: str, prepared: PreparedAttachment) -> AttachmentRow:
    return AttachmentRow(
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


def _advance_cursor(
    session: Session,
    account_id: str,
    uidvalidity: int,
    uid: int,
    synced_at: str,
) -> None:
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

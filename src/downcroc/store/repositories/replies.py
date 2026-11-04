from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from downcroc.domain.messages import (
    IncomingMessage,
    has_reply_prefix,
    normalize_subject,
)
from downcroc.runtime.clock import parse_utc
from downcroc.runtime.ids import new_id
from downcroc.store.db.models.batches import BatchRow
from downcroc.store.db.models.jobs import JobRow
from downcroc.store.db.models.messages import MessageRow, ThreadRow

DEFAULT_REPLY_WINDOW_DAYS = 60


@dataclass(frozen=True)
class Attribution:
    thread: ThreadRow
    relation: str
    method: str
    reply_state: str
    job_id: str | None
    root_job_id: str | None
    batch_id: str | None
    unattributed_reason: str | None = None


@dataclass(frozen=True)
class BatchTotals:
    inbound: int
    replies: int
    late_replies: int
    bounces: int


def resolve(
    session: Session,
    account_id: str,
    incoming: IncomingMessage,
    fallback_root: str,
) -> Attribution:
    if incoming.is_dsn:
        return _resolve_dsn(session, account_id, incoming, fallback_root)
    found = _resolve_headers(session, incoming)
    if found is not None:
        return found
    subject = _resolve_subject(session, incoming)
    if subject is not None:
        thread, job = subject
        return Attribution(
            thread=thread,
            relation="probable",
            method="subject",
            reply_state="probable",
            job_id=None,
            root_job_id=job.id,
            batch_id=thread.batch_id,
        )
    participant = _resolve_participant(session, incoming)
    if participant is not None:
        thread, job = participant
        return Attribution(
            thread=thread,
            relation="probable",
            method="participant",
            reply_state="probable",
            job_id=None,
            root_job_id=job.id,
            batch_id=thread.batch_id,
        )
    reason = None
    if incoming.in_reply_to or incoming.references:
        reason = "unknown_thread"
    elif has_reply_prefix(incoming.subject):
        reason = "subject_no_match"
    thread = _new_thread(session, incoming, fallback_root)
    return Attribution(
        thread=thread,
        relation="root",
        method="new",
        reply_state="none",
        job_id=None,
        root_job_id=None,
        batch_id=None,
        unattributed_reason=reason,
    )


def batch_totals(session: Session, batch_id: str, window_days: int) -> BatchTotals:
    rows = session.execute(
        select(MessageRow, ThreadRow, JobRow)
        .join(ThreadRow, MessageRow.thread_id == ThreadRow.id)
        .outerjoin(JobRow, ThreadRow.root_message_id == JobRow.message_id)
        .where(ThreadRow.batch_id == batch_id)
    ).all()
    inbound = 0
    replies = 0
    late = 0
    bounces = 0
    for message, _, job in rows:
        inbound += 1
        if message.is_dsn:
            bounces += 1
            continue
        if message.reply_state != "confirmed":
            continue
        replies += 1
        if _late(message.date, job, window_days):
            late += 1
    return BatchTotals(
        inbound=inbound,
        replies=replies,
        late_replies=late,
        bounces=bounces,
    )


def suppressed_address(session: Session, account_id: str, address: str) -> bool:
    row = session.scalar(
        select(MessageRow.id)
        .join(ThreadRow, MessageRow.thread_id == ThreadRow.id)
        .join(JobRow, ThreadRow.root_message_id == JobRow.message_id)
        .where(
            JobRow.account_id == account_id,
            MessageRow.from_address == address,
            MessageRow.reply_state == "confirmed",
            MessageRow.is_dsn.is_(False),
        )
        .limit(1)
    )
    return row is not None


def suppressed_addresses(session: Session, account_id: str) -> set[str]:
    rows = session.scalars(
        select(MessageRow.from_address)
        .join(ThreadRow, MessageRow.thread_id == ThreadRow.id)
        .join(JobRow, ThreadRow.root_message_id == JobRow.message_id)
        .where(
            JobRow.account_id == account_id,
            MessageRow.reply_state == "confirmed",
            MessageRow.is_dsn.is_(False),
        )
        .distinct()
    )
    return set(rows)


def _resolve_headers(session: Session, incoming: IncomingMessage) -> Attribution | None:
    values = [
        value
        for value in (incoming.in_reply_to, *reversed(incoming.references))
        if value
    ]
    for candidate in dict.fromkeys(values):
        job = _job_by_message_id(session, candidate)
        if job is not None:
            thread = _thread_for_job(session, job, incoming)
            return Attribution(
                thread=thread,
                relation="reply",
                method=_header_method(incoming, candidate),
                reply_state="confirmed",
                job_id=job.id,
                root_job_id=job.id,
                batch_id=thread.batch_id,
            )
        thread = _thread_by_message_id(session, candidate)
        if thread is None:
            continue
        root_job = _root_job(session, thread)
        return Attribution(
            thread=thread,
            relation="reply",
            method=_header_method(incoming, candidate),
            reply_state="confirmed" if root_job else "none",
            job_id=root_job.id if root_job else None,
            root_job_id=root_job.id if root_job else None,
            batch_id=thread.batch_id,
            unattributed_reason=None if root_job else "thread_not_job",
        )
    return None


def _resolve_dsn(
    session: Session,
    account_id: str,
    incoming: IncomingMessage,
    fallback_root: str,
) -> Attribution:
    job = _job_by_message_id(session, incoming.dsn_original_message_id)
    method = "dsn_original_message_id"
    if job is None:
        job = _job_by_recipient(session, account_id, incoming.dsn_recipient)
        method = "dsn_recipient"
    if job is not None:
        thread = _thread_for_job(session, job, incoming)
        return Attribution(
            thread=thread,
            relation="reply",
            method=method,
            reply_state="none",
            job_id=job.id,
            root_job_id=job.id,
            batch_id=thread.batch_id,
        )
    thread = _new_thread(session, incoming, fallback_root)
    return Attribution(
        thread=thread,
        relation="root",
        method="dsn_unmatched",
        reply_state="none",
        job_id=None,
        root_job_id=None,
        batch_id=None,
        unattributed_reason="dsn_unmatched",
    )


def _resolve_participant(
    session: Session, incoming: IncomingMessage
) -> tuple[ThreadRow, JobRow] | None:
    """Match a reply when the provider rewrote its Message-ID headers."""
    if not incoming.from_address:
        return None
    reply_shaped = bool(
        incoming.is_auto_reply
        or incoming.in_reply_to
        or incoming.references
        or has_reply_prefix(incoming.subject)
    )
    if not reply_shaped:
        return None
    jobs = session.scalars(
        select(JobRow)
        .where(
            JobRow.recipient == incoming.from_address,
            JobRow.batch_id != "manual",
            JobRow.state.in_(("sent", "sent_unconfirmed")),
        )
        .order_by(JobRow.sent_at.desc(), JobRow.created_at.desc())
    )
    windows: dict[str, int] = {}
    for job in jobs:
        if not _inside_window(session, job.batch_id, job, incoming.date, windows):
            continue
        return _thread_for_job(session, job, incoming), job
    return None


def _resolve_subject(
    session: Session, incoming: IncomingMessage
) -> tuple[ThreadRow, JobRow] | None:
    subject = normalize_subject(incoming.subject)
    if not subject or not incoming.from_address:
        return None
    jobs = session.scalars(
        select(JobRow)
        .where(
            JobRow.recipient == incoming.from_address,
            JobRow.batch_id != "manual",
            JobRow.state.in_(("sent", "sent_unconfirmed")),
        )
        .order_by(JobRow.sent_at.desc(), JobRow.created_at.desc())
    )
    windows: dict[str, int] = {}
    for job in jobs:
        if normalize_subject(job.subject) != subject:
            continue
        if not _inside_window(session, job.batch_id, job, incoming.date, windows):
            continue
        return _thread_for_job(session, job, incoming), job
    return None


def _thread_for_job(
    session: Session, job: JobRow, incoming: IncomingMessage
) -> ThreadRow:
    thread = session.scalar(
        select(ThreadRow).where(ThreadRow.root_message_id == job.message_id)
    )
    if thread is not None:
        if thread.batch_id is None:
            thread.batch_id = job.batch_id
        return thread
    subject = normalize_subject(job.subject) or normalize_subject(incoming.subject)
    thread = ThreadRow(
        id=new_id("thr"),
        root_message_id=job.message_id,
        subject=subject or "(no subject)",
        batch_id=job.batch_id,
        message_count=0,
        reply_count=0,
        first_seen=job.sent_at or incoming.date,
        last_seen=incoming.date,
    )
    session.add(thread)
    session.flush()
    return thread


def _new_thread(
    session: Session, incoming: IncomingMessage, fallback_root: str
) -> ThreadRow:
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
    return thread


def _job_by_message_id(session: Session, message_id: str | None) -> JobRow | None:
    if not message_id:
        return None
    return session.scalar(
        select(JobRow).where(JobRow.message_id == message_id).limit(1)
    )


def _job_by_recipient(
    session: Session, account_id: str, recipient: str | None
) -> JobRow | None:
    if not recipient:
        return None
    return session.scalar(
        select(JobRow)
        .where(
            JobRow.account_id == account_id,
            JobRow.recipient == recipient,
            JobRow.state == "sent",
        )
        .order_by(JobRow.sent_at.desc(), JobRow.created_at.desc())
        .limit(1)
    )


def _thread_by_message_id(session: Session, message_id: str) -> ThreadRow | None:
    row = session.execute(
        select(MessageRow.thread_id)
        .where(
            MessageRow.message_id == message_id,
            MessageRow.thread_id.is_not(None),
        )
        .order_by(MessageRow.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    return session.get(ThreadRow, row)


def _root_job(session: Session, thread: ThreadRow) -> JobRow | None:
    return session.scalar(
        select(JobRow).where(JobRow.message_id == thread.root_message_id).limit(1)
    )


def _inside_window(
    session: Session,
    batch_id: str | None,
    job: JobRow,
    date: str,
    cache: dict[str, int],
) -> bool:
    sent_at = job.sent_at or job.updated_at
    if not sent_at:
        return False
    days = _window_days(session, batch_id, cache)
    try:
        return parse_utc(date) <= parse_utc(sent_at) + timedelta(days=days)
    except ValueError:
        return False


def _late(date: str, job: JobRow | None, window_days: int) -> bool:
    if job is None or not job.sent_at:
        return False
    try:
        return parse_utc(date) > parse_utc(job.sent_at) + timedelta(days=window_days)
    except ValueError:
        return False


def _window_days(session: Session, batch_id: str | None, cache: dict[str, int]) -> int:
    if batch_id is None:
        return DEFAULT_REPLY_WINDOW_DAYS
    if batch_id in cache:
        return cache[batch_id]
    batch = session.get(BatchRow, batch_id)
    days = DEFAULT_REPLY_WINDOW_DAYS
    if batch is not None:
        try:
            options = json.loads(batch.options_json or "{}")
        except json.JSONDecodeError:
            options = {}
        value = options.get("reply_window_days")
        if isinstance(value, int) and value >= 0:
            days = value
    cache[batch_id] = days
    return days


def _header_method(incoming: IncomingMessage, candidate: str) -> str:
    if incoming.in_reply_to == candidate:
        return "in-reply-to"
    return "references"

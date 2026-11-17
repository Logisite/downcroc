from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import HoleStatus, ThreadHole
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.store.db.models import JobRow, SendAttemptRow

SENT_OUTCOMES = ("sent", "sent_unconfirmed", "uncertain")


@dataclass(frozen=True)
class HoleCounts:
    """One account's backfill holes, split by what the worker can do now."""

    account_id: str
    due: int = 0
    waiting: int = 0
    missing: int = 0
    unresolved: int = 0
    next_due_at: str | None = None

    @property
    def open(self) -> int:
        return self.due + self.waiting

    @property
    def total(self) -> int:
        return self.open + self.missing + self.unresolved


@dataclass(frozen=True)
class HoleDetail:
    """Everything the explain command needs about one hole."""

    attempt_id: str
    job_id: str
    account_id: str | None
    message_id: str | None
    outcome: str
    started_at: str
    finished_at: str | None
    provider_message_id: str | None
    provider_thread_id: str | None
    thread_status: str | None
    first_miss_at: str | None
    missing_at: str | None
    last_checked_at: str | None
    next_check_at: str | None
    check_count: int
    last_result: str | None
    last_scope: str | None
    last_error: str | None


def _base_conditions():
    return (
        SendAttemptRow.outcome.in_(SENT_OUTCOMES),
        SendAttemptRow.provider_thread_id.is_(None),
        JobRow.message_id.is_not(None),
        SendAttemptRow.account_id.is_not(None),
    )


def _to_hole(row: SendAttemptRow, message_id: str) -> ThreadHole:
    return ThreadHole(
        attempt_id=row.id,
        job_id=row.job_id,
        account_id=row.account_id or "",
        message_id=message_id,
        started_at=row.started_at,
        provider_message_id=row.provider_message_id,
        outcome=row.outcome,
        first_miss_at=row.thread_first_miss_at,
        next_check_at=row.thread_next_check_at,
        check_count=row.thread_check_count or 0,
        last_result=row.thread_last_result,
        thread_status=row.provider_thread_status,
    )


class ThreadBackfillRepo:
    """The durable state of the thread-id backfill.

    A hole is due when it is open and its next check is unset or past. New
    columns stay null on rows written before this engine existed, which makes
    those rows due on the first pass after an upgrade.
    """

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def counts(self, now: str | None = None) -> dict[str, HoleCounts]:
        moment = parse_utc(now or utc_now())
        with self._sessions() as session:
            rows = session.execute(
                select(
                    SendAttemptRow.account_id,
                    SendAttemptRow.provider_thread_status,
                    SendAttemptRow.thread_next_check_at,
                )
                .join(JobRow, JobRow.id == SendAttemptRow.job_id)
                .where(*_base_conditions())
            )
            grouped: dict[str, dict[str, object]] = {}
            for account_id, status, next_check_at in rows:
                state = grouped.setdefault(
                    account_id,
                    {
                        "due": 0,
                        "waiting": 0,
                        "missing": 0,
                        "unresolved": 0,
                        "next": None,
                    },
                )
                if status == HoleStatus.MISSING:
                    state["missing"] += 1
                    continue
                if status == HoleStatus.UNRESOLVED:
                    state["unresolved"] += 1
                    continue
                next_moment = (
                    parse_utc(next_check_at) if next_check_at is not None else None
                )
                if next_moment is not None and next_moment > moment:
                    state["waiting"] += 1
                    current = state["next"]
                    if current is None or next_moment < current:
                        state["next"] = next_moment
                else:
                    state["due"] += 1
            return {
                account_id: HoleCounts(
                    account_id=account_id,
                    due=int(state["due"]),
                    waiting=int(state["waiting"]),
                    missing=int(state["missing"]),
                    unresolved=int(state["unresolved"]),
                    next_due_at=_stamp(state["next"]),
                )
                for account_id, state in grouped.items()
            }

    def due_holes(
        self, account_id: str, limit: int, *, now: str | None = None
    ) -> list[ThreadHole]:
        moment = now or utc_now()
        with self._sessions() as session:
            rows = session.execute(
                select(SendAttemptRow, JobRow.message_id)
                .join(JobRow, JobRow.id == SendAttemptRow.job_id)
                .where(*_base_conditions())
                .where(SendAttemptRow.account_id == account_id)
                .where(SendAttemptRow.provider_thread_status.is_(None))
                .where(
                    or_(
                        SendAttemptRow.thread_next_check_at.is_(None),
                        SendAttemptRow.thread_next_check_at <= moment,
                    )
                )
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
                .limit(limit)
            )
            return [_to_hole(row, message_id) for row, message_id in rows]

    def detail(self, attempt_id: str) -> HoleDetail | None:
        with self._sessions() as session:
            found = session.execute(
                select(SendAttemptRow, JobRow.message_id)
                .join(JobRow, JobRow.id == SendAttemptRow.job_id)
                .where(SendAttemptRow.id == attempt_id)
            ).first()
            if found is None:
                return None
            row, message_id = found
            return HoleDetail(
                attempt_id=row.id,
                job_id=row.job_id,
                account_id=row.account_id,
                message_id=message_id,
                outcome=row.outcome,
                started_at=row.started_at,
                finished_at=row.finished_at,
                provider_message_id=row.provider_message_id,
                provider_thread_id=row.provider_thread_id,
                thread_status=row.provider_thread_status,
                first_miss_at=row.thread_first_miss_at,
                missing_at=row.thread_missing_at,
                last_checked_at=row.thread_last_checked_at,
                next_check_at=row.thread_next_check_at,
                check_count=row.thread_check_count or 0,
                last_result=row.thread_last_result,
                last_scope=row.thread_last_scope,
                last_error=row.thread_last_error,
            )

    def resolve(
        self,
        attempt_id: str,
        thread_id: str,
        *,
        scope: str,
        now: str | None = None,
    ) -> bool:
        moment = now or utc_now()
        with self._sessions.begin() as session:
            result = session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.id == attempt_id)
                .where(SendAttemptRow.provider_thread_id.is_(None))
                .values(
                    provider_thread_id=thread_id,
                    thread_last_checked_at=moment,
                    thread_next_check_at=None,
                    thread_check_count=SendAttemptRow.thread_check_count + 1,
                    thread_last_result="resolved",
                    thread_last_scope=scope,
                    thread_last_error=None,
                )
            )
            return bool(result.rowcount)

    def mark_waiting(
        self,
        attempt_id: str,
        *,
        next_check_at: str,
        result: str,
        scope: str | None,
        error: str | None = None,
        now: str | None = None,
    ) -> bool:
        moment = now or utc_now()
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None or row.provider_thread_id is not None:
                return False
            if row.provider_thread_status in {
                HoleStatus.MISSING,
                HoleStatus.UNRESOLVED,
            }:
                return False
            row.thread_last_checked_at = moment
            row.thread_next_check_at = next_check_at
            row.thread_check_count = (row.thread_check_count or 0) + 1
            row.thread_last_result = result
            row.thread_last_scope = scope
            row.thread_last_error = error
            if row.thread_first_miss_at is None:
                row.thread_first_miss_at = moment
            return True

    def mark_missing(
        self,
        attempt_id: str,
        *,
        scope: str | None,
        now: str | None = None,
    ) -> bool:
        return self._close(
            attempt_id,
            status=HoleStatus.MISSING,
            result="absent",
            scope=scope,
            error=None,
            now=now,
        )

    def mark_unresolved(
        self,
        attempt_id: str,
        *,
        scope: str | None,
        error: str | None,
        now: str | None = None,
    ) -> bool:
        return self._close(
            attempt_id,
            status=HoleStatus.UNRESOLVED,
            result="unresolved",
            scope=scope,
            error=error,
            now=now,
        )

    def _close(
        self,
        attempt_id: str,
        *,
        status: HoleStatus,
        result: str,
        scope: str | None,
        error: str | None,
        now: str | None,
    ) -> bool:
        moment = now or utc_now()
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None or row.provider_thread_id is not None:
                return False
            if row.provider_thread_status is not None:
                return False
            row.provider_thread_status = status
            row.thread_missing_at = moment
            row.thread_last_checked_at = moment
            row.thread_next_check_at = None
            row.thread_check_count = (row.thread_check_count or 0) + 1
            row.thread_last_result = result
            row.thread_last_scope = scope
            row.thread_last_error = error
            if row.thread_first_miss_at is None:
                row.thread_first_miss_at = moment
            return True

    def reopen(self, attempt_id: str, *, now: str | None = None) -> bool:
        moment = now or utc_now()
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None or row.provider_thread_id is not None:
                return False
            row.provider_thread_status = None
            row.thread_missing_at = None
            row.thread_next_check_at = moment
            row.thread_last_result = "reopened"
            return True


def _stamp(moment: object) -> str | None:
    if moment is None:
        return None
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")

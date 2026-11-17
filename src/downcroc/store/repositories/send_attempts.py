from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.attempts import SendAttempt, ThreadHole
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.store.db.models import JobRow, SendAttemptRow

SENT_OUTCOMES = ("sent", "sent_unconfirmed", "uncertain")


def _hole_conditions():
    return (
        SendAttemptRow.outcome.in_(SENT_OUTCOMES),
        SendAttemptRow.provider_thread_id.is_(None),
        SendAttemptRow.provider_thread_status.is_(None),
        JobRow.message_id.is_not(None),
    )


def _to_attempt(row: SendAttemptRow) -> SendAttempt:
    return SendAttempt(
        id=row.id,
        job_id=row.job_id,
        account_id=row.account_id,
        binding_id=row.binding_id,
        transport=row.transport,
        started_at=row.started_at,
        finished_at=row.finished_at,
        outcome=row.outcome,
        accepted=row.accepted,
        error_code=row.error_code,
        error_message=row.error_message,
        provider_message_id=row.provider_message_id,
        provider_thread_id=getattr(row, "provider_thread_id", None),
        detail=row.detail,
        quota_day=row.quota_day,
        quota_state=row.quota_state,
    )


class SendAttemptRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, attempt: SendAttempt) -> SendAttempt:
        row = SendAttemptRow(
            id=attempt.id,
            job_id=attempt.job_id,
            account_id=attempt.account_id,
            binding_id=attempt.binding_id,
            transport=attempt.transport,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            outcome=attempt.outcome,
            accepted=attempt.accepted,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            provider_message_id=attempt.provider_message_id,
            provider_thread_id=attempt.provider_thread_id,
            detail=attempt.detail,
            quota_day=attempt.quota_day,
            quota_state=attempt.quota_state,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return attempt

    def create_reserved(
        self,
        attempt_id: str,
        job_id: str,
        account_id: str,
        day: str,
        started_at: str,
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                SendAttemptRow(
                    id=attempt_id,
                    job_id=job_id,
                    account_id=account_id,
                    binding_id=None,
                    transport="pending",
                    started_at=started_at,
                    finished_at=None,
                    outcome="reserved",
                    accepted=None,
                    error_code=None,
                    error_message=None,
                    provider_message_id=None,
                    detail=None,
                    quota_day=day,
                    quota_state="reserved",
                )
            )

    def finish(
        self,
        attempt_id: str,
        *,
        binding_id: str | None,
        transport: str,
        outcome: str,
        accepted: bool | None,
        code: str | None,
        message: str | None,
        provider_message_id: str | None,
        provider_thread_id: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None or row.outcome != "reserved":
                return
            row.binding_id = binding_id
            row.transport = transport
            row.outcome = outcome
            row.accepted = accepted
            row.error_code = code
            row.error_message = message
            row.provider_message_id = provider_message_id
            row.provider_thread_id = provider_thread_id
            row.finished_at = utc_now()

    def reserved_accepted(self) -> list[SendAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.quota_state == "reserved")
                .where(
                    SendAttemptRow.outcome.in_(
                        ("sent", "sent_unconfirmed", "uncertain")
                    )
                )
            )
            return [_to_attempt(row) for row in rows]

    def attribution(self) -> dict[str, str]:
        """Map job id to the account of its latest attributed attempt.

        Auto-routed jobs deliberately keep ``account_id`` empty on the job row,
        so the account that actually carried the message only exists here.
        """
        with self._sessions() as session:
            rows = session.execute(
                select(
                    SendAttemptRow.job_id,
                    SendAttemptRow.account_id,
                )
                .where(SendAttemptRow.account_id.is_not(None))
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
            )
            return {row[0]: row[1] for row in rows}

    def latest_for_job(self, job_id: str) -> SendAttempt | None:
        with self._sessions() as session:
            row = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at.desc(), SendAttemptRow.id.desc())
                .limit(1)
            ).first()
            return None if row is None else _to_attempt(row)

    def provider_thread_id_for_job(
        self, job_id: str, *, account_id: str | None = None
    ) -> str | None:
        with self._sessions() as session:
            stmt = (
                select(SendAttemptRow.provider_thread_id)
                .where(SendAttemptRow.job_id == job_id)
                .where(SendAttemptRow.provider_thread_id.is_not(None))
                .where(
                    SendAttemptRow.outcome.in_(
                        ("sent", "sent_unconfirmed", "uncertain")
                    )
                )
            )
            if account_id is not None:
                stmt = stmt.where(SendAttemptRow.account_id == account_id)
            stmt = stmt.order_by(
                SendAttemptRow.started_at.desc(), SendAttemptRow.id.desc()
            ).limit(1)
            value = session.scalars(stmt).first()
            return str(value) if value else None

    def quota_state(self, attempt_id: str) -> str | None:
        with self._sessions() as session:
            row = session.get(SendAttemptRow, attempt_id)
            return None if row is None else row.quota_state

    def set_quota(self, attempt_id: str, day: str, state: str) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.id == attempt_id)
                .values(quota_day=day, quota_state=state)
            )

    def reconcile_interrupted(self) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.outcome == "reserved")
                .values(
                    outcome="interrupted",
                    finished_at=utc_now(),
                    quota_state="released",
                )
            )
            return int(result.rowcount or 0)

    def release_reserved(self) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.quota_state == "reserved")
                .values(quota_state="released")
            )
            return int(result.rowcount or 0)

    def list_for_job(self, job_id: str) -> list[SendAttempt]:
        with self._sessions() as session:
            rows = session.scalars(
                select(SendAttemptRow)
                .where(SendAttemptRow.job_id == job_id)
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
            )
            return [_to_attempt(row) for row in rows]

    def thread_hole_counts(self) -> dict[str, int]:
        """Holes per account: sent attempts still missing a provider thread id."""

        with self._sessions() as session:
            rows = session.execute(
                select(SendAttemptRow.account_id, func.count())
                .join(JobRow, JobRow.id == SendAttemptRow.job_id)
                .where(*_hole_conditions())
                .where(SendAttemptRow.account_id.is_not(None))
                .group_by(SendAttemptRow.account_id)
            )
            return {row[0]: int(row[1]) for row in rows}

    def thread_holes(self, account_id: str, page_size: int) -> list[ThreadHole]:
        """Oldest eligible holes for one account, page_size at a time."""

        with self._sessions() as session:
            rows = session.execute(
                select(
                    SendAttemptRow.id,
                    SendAttemptRow.job_id,
                    SendAttemptRow.account_id,
                    JobRow.message_id,
                    SendAttemptRow.started_at,
                    SendAttemptRow.provider_message_id,
                )
                .join(JobRow, JobRow.id == SendAttemptRow.job_id)
                .where(*_hole_conditions())
                .where(SendAttemptRow.account_id == account_id)
                .order_by(SendAttemptRow.started_at, SendAttemptRow.id)
                .limit(page_size)
            )
            return [
                ThreadHole(
                    attempt_id=row[0],
                    job_id=row[1],
                    account_id=row[2],
                    message_id=row[3],
                    started_at=row[4],
                    provider_message_id=row[5],
                )
                for row in rows
            ]

    def resolve_thread(self, attempt_id: str, thread_id: str) -> bool:
        """Write the thread id unless a concurrent writer filled the hole first."""

        with self._sessions.begin() as session:
            result = session.execute(
                update(SendAttemptRow)
                .where(SendAttemptRow.id == attempt_id)
                .where(SendAttemptRow.provider_thread_id.is_(None))
                .values(provider_thread_id=thread_id)
            )
            return bool(result.rowcount)

    def miss_thread(self, attempt_id: str, *, retry_after_days: int) -> str:
        """Record one failed lookup: first, waiting, missing, or resolved."""

        now = utc_now()
        with self._sessions.begin() as session:
            row = session.get(SendAttemptRow, attempt_id)
            if row is None or row.provider_thread_id is not None:
                return "resolved"
            if row.provider_thread_status == "missing":
                return "missing"
            if row.thread_first_miss_at is None:
                row.thread_first_miss_at = now
                return "first"
            first = parse_utc(row.thread_first_miss_at)
            moment = parse_utc(now)
            if (
                first is not None
                and moment is not None
                and (moment - first).total_seconds() < retry_after_days * 86_400
            ):
                return "waiting"
            row.provider_thread_status = "missing"
            row.thread_missing_at = now
            return "missing"

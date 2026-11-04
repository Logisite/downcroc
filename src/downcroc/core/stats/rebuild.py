from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from downcroc.core.policy import PolicyResolver
from downcroc.core.stats.counters import BatchCounterUpdater
from downcroc.core.stats.range import local_today, parse_day
from downcroc.domain.activity import ACTIVITY_FIELDS
from downcroc.runtime.clock import parse_utc
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.activity import ActivityRepo, day_key, hour_key
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo

SENT_STATES = frozenset({"sent", "sent_unconfirmed"})


@dataclass(frozen=True)
class RebuildResult:
    since: str | None
    rows: int
    duration_ms: int


class RebuildService:
    def __init__(
        self,
        activity: ActivityRepo,
        accounts: AccountRepo,
        jobs: JobRepo,
        messages: MessageRepo,
        send_attempts: SendAttemptRepo,
        counters: BatchCounterUpdater,
        policy: PolicyResolver,
        log: EventLogger,
    ) -> None:
        self._activity = activity
        self._accounts = accounts
        self._jobs = jobs
        self._messages = messages
        self._send_attempts = send_attempts
        self._counters = counters
        self._policy = policy
        self._log = log

    def run(self, since: str | None) -> RebuildResult:
        started = time.monotonic()
        requested = _since_day(since)
        end_day = local_today().isoformat()
        job_rows = self._jobs.activity_rows()
        message_rows = self._messages.activity_rows()
        covered = requested or _earliest_day(job_rows, message_rows)

        if covered is not None:
            before_stored = self._stored(covered, end_day)
            before_rows = _count_sent(job_rows, covered, end_day)
            if before_stored != before_rows:
                self._log.warning(
                    "stats.invariant",
                    outcome="mismatch",
                    stored=before_stored,
                    rows=before_rows,
                )

        allowances = {
            account.id: self._policy.effective(account).daily_allowance
            for account in self._accounts.list()
        }
        if covered is None:
            activity_rows = 0
        else:
            hourly, daily = _build_activity(
                job_rows,
                message_rows,
                covered,
                allowances,
                self._send_attempts.attribution(),
            )
            _merge_suppressed(
                hourly,
                daily,
                self._activity.suppressed(covered),
                allowances,
            )
            activity_rows = self._activity.replace(covered, hourly, daily)

        batch_rows = self._counters.refresh_all()

        if covered is not None:
            after_stored = self._stored(covered, end_day)
            after_rows = _count_sent(job_rows, covered, end_day)
            self._log.info(
                "stats.invariant",
                outcome="ok" if after_stored == after_rows else "mismatch",
                stored=after_stored,
                rows=after_rows,
            )
        duration_ms = round((time.monotonic() - started) * 1000)
        self._log.info(
            "stats.rebuilt",
            since=requested or "all",
            rows=activity_rows + batch_rows,
            duration_ms=duration_ms,
        )
        return RebuildResult(
            since=requested,
            rows=activity_rows + batch_rows,
            duration_ms=duration_ms,
        )

    def _stored(self, since_day: str | None, end_day: str) -> int:
        return self._activity.stored_sent(since_day or "0000-01-01", end_day)


def _since_day(since: str | None) -> str | None:
    chosen = parse_day(since)
    return None if chosen is None else chosen.isoformat()


def _build_activity(
    job_rows: list[tuple[str, str | None, str | None, str | None, str]],
    message_rows: list[tuple[str, str, bool, str, str | None]],
    since_day: str | None,
    allowances: dict[str, int],
    attribution: dict[str, str],
) -> tuple[
    dict[tuple[str, str], dict[str, int]], dict[tuple[str, str], dict[str, int]]
]:
    hourly: dict[tuple[str, str], dict[str, int]] = {}
    daily: dict[tuple[str, str], dict[str, int]] = {}

    for job_id, account_id, sent_at, updated_at, state in job_rows:
        account_id = account_id or attribution.get(job_id)
        if account_id is None:
            continue
        if state in SENT_STATES and sent_at:
            _bump(hourly, daily, account_id, sent_at, "sent", since_day, allowances)
        if state == "failed" and updated_at:
            _bump(
                hourly, daily, account_id, updated_at, "failed", since_day, allowances
            )

    for account_id, ingested_at, is_dsn, reply_state, job_id in message_rows:
        _bump(hourly, daily, account_id, ingested_at, "received", since_day, allowances)
        if reply_state == "confirmed":
            _bump(
                hourly,
                daily,
                account_id,
                ingested_at,
                "replies",
                since_day,
                allowances,
            )
        if is_dsn and job_id is not None:
            _bump(
                hourly,
                daily,
                account_id,
                ingested_at,
                "bounces",
                since_day,
                allowances,
            )
    return hourly, daily


def _bump(
    hourly: dict[tuple[str, str], dict[str, int]],
    daily: dict[tuple[str, str], dict[str, int]],
    account_id: str,
    stamp: str,
    field: str,
    since_day: str | None,
    allowances: dict[str, int],
) -> None:
    try:
        moment = parse_utc(stamp)
    except ValueError:
        return
    day = day_key(moment)
    if since_day is not None and day < since_day:
        return
    hour = hour_key(moment)
    hkey = (account_id, hour)
    dkey = (account_id, day)
    hourly.setdefault(hkey, _blank())
    daily.setdefault(dkey, {**_blank(), "quota_limit": allowances.get(account_id, 0)})
    hourly[hkey][field] += 1
    daily[dkey][field] += 1


def _merge_suppressed(
    hourly: dict[tuple[str, str], dict[str, int]],
    daily: dict[tuple[str, str], dict[str, int]],
    suppressed: tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]],
    allowances: dict[str, int],
) -> None:
    hourly_suppressed, daily_suppressed = suppressed
    for key, value in hourly_suppressed.items():
        hourly.setdefault(key, _blank())["suppressed"] = value
    for key, value in daily_suppressed.items():
        extras = {"quota_limit": allowances.get(key[0], 0)}
        daily.setdefault(key, {**_blank(), **extras})["suppressed"] = value


def _blank() -> dict[str, int]:
    return {field: 0 for field in ACTIVITY_FIELDS}


def _earliest_day(
    job_rows: list[tuple[str, str | None, str | None, str]],
    message_rows: list[tuple[str, str, bool, str, str | None]],
) -> str | None:
    days: list[str] = []
    for _, sent_at, updated_at, state in job_rows:
        if state in SENT_STATES:
            stamp = sent_at
        elif state == "failed":
            stamp = updated_at
        else:
            stamp = None
        if stamp:
            day = _day(stamp)
            if day is not None:
                days.append(day)
    for _, ingested_at, _, _, _ in message_rows:
        day = _day(ingested_at)
        if day is not None:
            days.append(day)
    return min(days) if days else None


def _day(stamp: str) -> str | None:
    try:
        return day_key(parse_utc(stamp))
    except ValueError:
        return None


def _count_sent(
    job_rows: list[tuple[str, str | None, str | None, str]],
    since_day: str | None,
    end_day: str,
) -> int:
    total = 0
    for _, sent_at, _, state in job_rows:
        if state not in SENT_STATES or not sent_at:
            continue
        try:
            moment: datetime = parse_utc(sent_at)
        except ValueError:
            continue
        day = day_key(moment)
        if (since_day is None or day >= since_day) and day <= end_day:
            total += 1
    return total

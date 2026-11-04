from __future__ import annotations

from datetime import datetime

from downcroc.core.policy import PolicyResolver
from downcroc.core.stats.counters import BatchCounterUpdater
from downcroc.core.stats.range import StatsRange, parse_range
from downcroc.core.stats.rebuild import RebuildResult, RebuildService
from downcroc.domain.accounts import Account
from downcroc.domain.activity import (
    AccountStats,
    ActivitySummary,
    ActivityTotals,
    BatchCounters,
    BatchStats,
    DailyActivity,
    HourlyActivity,
)
from downcroc.domain.errors import AccountNotFound
from downcroc.domain.jobs import Job
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.activity import ActivityRepo, day_key
from downcroc.store.repositories.batch_counters import BatchCounterRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class StatsService:
    def __init__(
        self,
        settings: Settings,
        activity: ActivityRepo,
        counters: BatchCounterRepo,
        batches: BatchRepo,
        jobs: JobRepo,
        messages: MessageRepo,
        accounts: AccountRepo,
        quota: QuotaRepo,
        policy: PolicyResolver,
        log: EventLogger,
        send_attempts: SendAttemptRepo,
    ) -> None:
        self._settings = settings
        self._activity = activity
        self._counters = counters
        self._batches = batches
        self._jobs = jobs
        self._messages = messages
        self._accounts = accounts
        self._quota = quota
        self._policy = policy
        self._log = log
        self._updater = BatchCounterUpdater(batches, jobs, messages, counters)
        self._rebuilder = RebuildService(
            activity,
            accounts,
            jobs,
            messages,
            send_attempts,
            self._updater,
            policy,
            log,
        )

    def record_sent(
        self,
        job: Job,
        account_id: str | None = None,
        moment: datetime | None = None,
    ) -> None:
        self._add(self._attribution(job, account_id), {"sent": 1}, moment)
        self.touch_batch(job.batch_id)

    def record_failed(
        self,
        job: Job,
        account_id: str | None = None,
        moment: datetime | None = None,
    ) -> None:
        self._add(self._attribution(job, account_id), {"failed": 1}, moment)
        self.touch_batch(job.batch_id)

    def record_inbound(
        self,
        account_id: str,
        *,
        confirmed: bool,
        is_dsn: bool,
        attributed: bool,
        batch_id: str | None,
    ) -> None:
        deltas = {"received": 1}
        if confirmed:
            deltas["replies"] = 1
        if is_dsn and attributed:
            deltas["bounces"] = 1
        self._add(account_id, deltas, None)
        if batch_id is not None:
            self.touch_batch(batch_id)

    def record_suppressed(self, batch_id: str, account_id: str, count: int) -> None:
        if count <= 0:
            return
        self._add(account_id, {"suppressed": count}, None)
        self.touch_batch(batch_id, suppressed_delta=count)

    def touch_batch(
        self,
        batch_id: str,
        *,
        suppressed_delta: int = 0,
        invalid_delta: int = 0,
    ) -> None:
        self._updater.touch(
            batch_id,
            suppressed_delta=suppressed_delta,
            invalid_delta=invalid_delta,
        )

    def summary(
        self, from_value: str | None, to_value: str | None, account_id: str | None
    ) -> tuple[StatsRange, ActivitySummary]:
        chosen = parse_range(from_value, to_value)
        return chosen, self._activity.summary(
            chosen.start_day, chosen.end_day, account_id
        )

    def hourly(
        self, from_value: str | None, to_value: str | None, account_id: str | None
    ) -> tuple[StatsRange, tuple[HourlyActivity, ...]]:
        chosen = parse_range(from_value, to_value)
        return chosen, self._activity.hourly(
            chosen.start_hour, chosen.end_hour, account_id
        )

    def daily(
        self, from_value: str | None, to_value: str | None, account_id: str | None
    ) -> tuple[StatsRange, tuple[DailyActivity, ...]]:
        chosen = parse_range(from_value, to_value)
        return chosen, self._activity.daily(
            chosen.start_day, chosen.end_day, account_id
        )

    def accounts_for(
        self,
        from_value: str | None,
        to_value: str | None,
        account_id: str | None = None,
    ) -> tuple[StatsRange, tuple[AccountStats, ...]]:
        chosen = parse_range(from_value, to_value)
        summary = self._activity.summary(chosen.start_day, chosen.end_day)
        by_id = {item.account_id: item.totals for item in summary.accounts}
        today = self._policy.day()
        rows = []
        for account in self._accounts.list():
            if account_id is not None and account.id != account_id:
                continue
            used, reserved = self._quota.status(account.id, today)
            allowance = self._policy.effective(account).daily_allowance
            rows.append(
                AccountStats(
                    account_id=account.id,
                    address=account.address,
                    totals=by_id.get(account.id, ActivityTotals()),
                    remaining_allowance=max(0, allowance - used - reserved),
                    used=used,
                    reserved=reserved,
                    available=max(0, allowance - used - reserved),
                )
            )
        return chosen, tuple(rows)

    def batches_for(
        self, from_value: str | None, to_value: str | None
    ) -> tuple[StatsRange, tuple[BatchStats, ...]]:
        chosen = parse_range(from_value, to_value)
        counters = {item.batch_id: item for item in self._counters.list(limit=10_000)}
        rows = []
        for batch in self._batches.list(limit=10_000):
            if not _inside(batch.created_at, chosen):
                continue
            counts = counters.get(batch.id) or _empty(batch.id)
            reply_rate = counts.replies / counts.sent if counts.sent else 0.0
            rows.append(
                BatchStats(
                    batch_id=batch.id,
                    kind=batch.kind.value,
                    name=batch.name,
                    counters=counts,
                    reply_rate=round(reply_rate, 4),
                )
            )
        return chosen, tuple(rows)

    def rebuild(self, since: str | None) -> RebuildResult:
        return self._rebuilder.run(since)

    def _attribution(self, job: Job, account_id: str | None) -> str:
        chosen = account_id or job.account_id
        if chosen is None:
            raise ValueError(f"job {job.id} has no account to attribute activity to")
        return chosen

    def _add(
        self,
        account_id: str,
        deltas: dict[str, int],
        moment: datetime | None,
    ) -> None:
        limit = self._allowance(account_id)
        self._activity.add(
            account_id, moment or parse_utc(utc_now()), deltas, quota_limit=limit
        )
        for field, value in deltas.items():
            self._log.debug(
                "stats.increment",
                account=account_id,
                field=field,
                value=value,
            )

    def _allowance(self, account_id: str) -> int:
        try:
            account: Account = self._accounts.get(account_id)
        except AccountNotFound:
            return self._settings.sending.daily_allowance
        return self._policy.effective(account).daily_allowance


def _inside(created_at: str, chosen: StatsRange) -> bool:
    try:
        day = day_key(parse_utc(created_at))
    except ValueError:
        day = created_at[:10]
    return chosen.start_day <= day <= chosen.end_day


def _empty(batch_id: str) -> BatchCounters:
    return BatchCounters(
        batch_id=batch_id,
        queued=0,
        sent=0,
        failed=0,
        suppressed=0,
        invalid=0,
        inbound=0,
        replies=0,
        late_replies=0,
        bounces=0,
        updated_at="",
    )

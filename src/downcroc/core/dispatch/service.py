from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.dispatch import eligibility, retry
from downcroc.core.dispatch.failures import FailureService
from downcroc.core.events import EventBus
from downcroc.core.followups import FollowUpService
from downcroc.core.outbound import OutboundService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import BatchNotFound, DomainError
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.quota import QuotaRepo


@dataclass
class Candidate:
    account: Account
    jobs: list[Job]
    remaining: int


class Dispatcher:
    def __init__(
        self,
        settings: Settings,
        jobs: JobRepo,
        accounts: AccountRepo,
        batches: BatchRepo,
        quota: QuotaRepo,
        failures: FailureService,
        followups: FollowUpService,
        outbound: OutboundService,
        vault: VaultService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._dispatch = settings.dispatch
        self._outbound_settings = settings.outbound
        self._followup_settings = settings.followups
        self._jobs = jobs
        self._accounts = accounts
        self._batches = batches
        self._quota = quota
        self._failures = failures
        self._followups = followups
        self._outbound = outbound
        self._vault = vault
        self._bus = bus
        self._log = log
        self._owner = f"dispatch-{uuid.uuid4().hex[:12]}"
        self._rng = random.Random()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._next_allowed: dict[str, float] = {}
        self._next_followup = 0.0

    def start(self) -> None:
        if self._task is not None:
            return
        self._failures.reconcile()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=self._dispatch.shutdown_join_s)
        except TimeoutError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._cycle()
            except asyncio.CancelledError:
                raise
            except (
                DomainError,
                OSError,
                RuntimeError,
                SQLAlchemyError,
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                self._log.error(
                    "dispatch.error",
                    error=error.__class__.__name__,
                    detail=str(error)[:200],
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._dispatch.tick_s)
            except TimeoutError:
                continue

    async def _cycle(self) -> None:
        if self._vault.status().state != "unlocked":
            return
        await asyncio.to_thread(self._followups.cancel_stopped)
        if time.monotonic() >= self._next_followup:
            try:
                await asyncio.to_thread(self._followups.plan_due)
            finally:
                self._next_followup = time.monotonic() + self._followup_settings.check_s
        started = time.monotonic()
        moment = eligibility.local_now()
        day = eligibility.day_key(moment)
        now = utc_now()
        now_utc = parse_utc(now)
        cache: dict[str, Batch | None] = {}
        candidates: list[Candidate] = []
        due_accounts = 0
        blocked_window = 0
        blocked_allowance = 0
        auto_pool = [
            job
            for job in self._jobs.due_auto(now)
            if self._batch_ready(job, now_utc, cache)
        ]
        for account in self._accounts.list():
            if not self._can_send(account):
                continue
            due = [
                job
                for job in self._jobs.due(account.id, now)
                if self._batch_ready(job, now_utc, cache)
            ]
            if not due and not auto_pool:
                continue
            due_accounts += 1
            if not eligibility.inside_window(account.policy, moment):
                blocked_window += 1
                continue
            used = self._quota.used(account.id, day)
            remaining = account.policy.daily_allowance - used
            if remaining <= 0:
                blocked_allowance += 1
                continue
            if time.monotonic() < self._next_allowed.get(account.id, 0.0):
                continue
            candidates.append(Candidate(account, due, remaining))
        if not candidates:
            self._idle(due_accounts, blocked_window, blocked_allowance)
            self._log_cycle(0, 0, 0, started)
            return
        capacity = self._dispatch.global_in_flight
        picked: list[tuple[Job, Account]] = []
        while candidates and len(picked) < capacity:
            candidate = self._weighted(candidates)
            job = candidate.jobs.pop(0) if candidate.jobs else None
            if job is None and auto_pool:
                job = auto_pool.pop(0)
            if job is None:
                candidates.remove(candidate)
                continue
            claimed = self._claim(candidate.account, job)
            if claimed is None:
                if not candidate.jobs:
                    candidates.remove(candidate)
                continue
            used = self._quota.consume(
                candidate.account.id,
                day,
                candidate.account.policy.daily_allowance,
            )
            if used is None:
                self._jobs.mark_queued(claimed.id, code="allowance_spent")
                candidates.remove(candidate)
                continue
            self._log.debug(
                "job.leased",
                job=claimed.id,
                account=candidate.account.id,
            )
            self._log.info(
                "quota.consumed",
                account=candidate.account.id,
                used=used,
                limit=candidate.account.policy.daily_allowance,
            )
            picked.append((claimed, candidate.account))
            candidate.remaining -= 1
            per_account = sum(
                1 for _, account in picked if account.id == candidate.account.id
            )
            if (
                per_account >= candidate.account.policy.max_in_flight
                or candidate.remaining <= 0
                or (not candidate.jobs and not auto_pool)
            ):
                candidates.remove(candidate)
        results = await asyncio.gather(
            *(self._send(job, account) for job, account in picked)
        )
        sent = sum(1 for result in results if result == "sent")
        failed = sum(1 for result in results if result == "failed")
        deferred = len(results) - sent - failed
        self._apply_spacing(picked)
        self._log_cycle(len(picked), sent, deferred, started)
        self._finalize({job.batch_id for job, _ in picked})
        if failed:
            self._log.debug("dispatch.failed", count=failed)

    def _can_send(self, account: Account) -> bool:
        return (
            account.status is AccountStatus.CONNECTED
            and account.policy.enabled
            and account.credential_present
            and account.archived_at is None
        )

    def _batch_ready(
        self, job: Job, now: datetime, cache: dict[str, Batch | None]
    ) -> bool:
        if job.batch_id not in cache:
            try:
                cache[job.batch_id] = self._batches.get(job.batch_id)
            except BatchNotFound:
                cache[job.batch_id] = None
        batch = cache[job.batch_id]
        if batch is None or batch.state is not BatchState.SENDING:
            return False
        try:
            options = json.loads(batch.options_json or "{}")
        except json.JSONDecodeError:
            return True
        floor = options.get("not_before")
        if not floor:
            return True
        try:
            return parse_utc(str(floor)) <= now
        except ValueError:
            return True

    def _claim(self, account: Account, job: Job) -> Job | None:
        return self._jobs.claim(
            job.id,
            self._owner,
            utc_now(),
            utc_after(self._outbound_settings.lease_seconds),
        )

    def _weighted(self, candidates: list[Candidate]) -> Candidate:
        weights = [max(1, candidate.remaining) for candidate in candidates]
        return self._rng.choices(candidates, weights=weights, k=1)[0]

    async def _send(self, job: Job, account: Account) -> str:
        try:
            result = await self._outbound.deliver(job, account)
        except DomainError as error:
            self._log.debug("dispatch.error", job=job.id, code=error.code)
            result = self._jobs.get(job.id)
        except (OSError, RuntimeError, SQLAlchemyError, ValueError) as error:
            self._log.error(
                "dispatch.error",
                job=job.id,
                error=error.__class__.__name__,
                detail=str(error)[:300],
            )
            result = self._jobs.get(job.id)
            if result.state is JobState.SENDING:
                result = self._jobs.mark_retry(
                    job.id,
                    code="dispatch_error",
                    message=error.__class__.__name__,
                    next_attempt_at=utc_now(),
                    retryable=True,
                )
        return self._settle(result, account.id)

    def _settle(self, job: Job, account_id: str) -> str:
        if job.state is JobState.SENT:
            return "sent"
        if job.state is JobState.FAILED:
            self._failures.record(job, account_id)
            return "failed"
        if job.state is JobState.RETRY_WAIT:
            return self._retry_or_fail(job, account_id)
        if job.state is JobState.QUEUED and job.retryable:
            return self._retry_or_fail(job, account_id)
        return "deferred"

    def _retry_or_fail(self, job: Job, account_id: str) -> str:
        if job.attempts >= self._dispatch.max_attempts:
            failed = self._jobs.mark_failed(
                job.id,
                code=job.last_error_code or "retry_exhausted",
                message=job.last_error_message or "",
                retryable=True,
            )
            self._failures.record(failed, account_id)
            return "failed"
        delay = retry.backoff_seconds(
            job.attempts,
            self._dispatch,
            self._rng,
        )
        self._jobs.mark_retry(
            job.id,
            code=job.last_error_code or "retry",
            message=job.last_error_message or "",
            next_attempt_at=utc_after(delay),
            retryable=True,
        )
        self._log.info(
            "job.retry",
            job=job.id,
            attempt=job.attempts,
            in_s=delay,
            code=job.last_error_code or "retry",
        )
        return "deferred"

    def _apply_spacing(self, picked: list[tuple[Job, Account]]) -> None:
        seen: set[str] = set()
        for _, account in picked:
            if account.id in seen:
                continue
            seen.add(account.id)
            low = account.policy.jitter_min
            high = account.policy.jitter_max
            if high <= 0:
                self._next_allowed.pop(account.id, None)
                continue
            delay = self._rng.uniform(low, high)
            self._next_allowed[account.id] = time.monotonic() + delay
            self._log.debug("dispatch.spacing", delay_ms=round(delay * 1000))

    def _idle(self, due: int, window: int, allowance: int) -> None:
        if due == 0:
            reason = "nothing due"
        elif window >= due:
            reason = "window closed"
        elif allowance >= due:
            reason = "allowance spent"
        else:
            reason = "nothing due"
        self._log.debug("dispatch.idle", reason=reason)

    def _log_cycle(self, picked: int, sent: int, deferred: int, started: float) -> None:
        self._log.debug(
            "dispatch.cycle",
            picked=picked,
            sent=sent,
            deferred=deferred,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )

    def _finalize(self, batch_ids: set[str]) -> None:
        active = {
            JobState.AWAITING_APPROVAL.value,
            JobState.QUEUED.value,
            JobState.SENDING.value,
            JobState.RETRY_WAIT.value,
        }
        for batch_id in batch_ids:
            try:
                batch = self._batches.get(batch_id)
            except BatchNotFound:
                continue
            if batch.state is not BatchState.SENDING:
                continue
            counts = self._jobs.counts(batch_id)
            if active & set(counts):
                continue
            done = self._batches.set_state(batch.id, BatchState.DONE)
            self._log.info(
                "batch.done",
                batch=done.id,
                sent=counts.get(JobState.SENT.value, 0),
                failed=counts.get(JobState.FAILED.value, 0),
            )
            self._bus.publish(
                "batch.completed",
                {
                    "batch_id": done.id,
                    "sent": counts.get(JobState.SENT.value, 0),
                    "failed": counts.get(JobState.FAILED.value, 0),
                },
            )

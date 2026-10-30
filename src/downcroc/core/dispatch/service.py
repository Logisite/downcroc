from __future__ import annotations

import asyncio
import contextlib
import random
import time
import uuid

from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.dispatch import eligibility, retry
from downcroc.core.dispatch.failures import FailureService
from downcroc.core.dispatch.helpers import Candidate, DispatchHelpers
from downcroc.core.events import EventBus
from downcroc.core.followups import FollowUpService
from downcroc.core.outbound import OutboundService
from downcroc.core.policy import PolicyResolver
from downcroc.core.transports import TransportService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import BatchNotFound, DomainError
from downcroc.domain.jobs import Job, JobState
from downcroc.domain.policy import SendPolicy
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.quota import QuotaRepo


class Dispatcher(DispatchHelpers):
    def __init__(
        self,
        settings: Settings,
        jobs: JobRepo,
        accounts: AccountRepo,
        transports: TransportService,
        batches: BatchRepo,
        quota: QuotaRepo,
        failures: FailureService,
        followups: FollowUpService,
        outbound: OutboundService,
        vault: VaultService,
        policy: PolicyResolver,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._dispatch = settings.dispatch
        self._outbound_settings = settings.outbound
        self._followup_settings = settings.followups
        self._jobs = jobs
        self._accounts = accounts
        self._transports = transports
        self._batches = batches
        self._quota = quota
        self._failures = failures
        self._followups = followups
        self._outbound = outbound
        self._vault = vault
        self._policy = policy
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
        await self._outbound.reap_sessions()
        await asyncio.to_thread(self._followups.cancel_stopped)
        if time.monotonic() >= self._next_followup:
            try:
                await asyncio.to_thread(self._followups.plan_due)
            finally:
                self._next_followup = time.monotonic() + self._followup_settings.check_s
        started = time.monotonic()
        moment = self._policy.now()
        day = self._policy.day(moment)
        now = utc_now()
        now_utc = parse_utc(now)
        cache: dict[str, Batch | None] = {}
        policies: dict[str, SendPolicy] = {}
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
            policy = self._policy.effective(account)
            policies[account.id] = policy
            due = [
                job
                for job in self._jobs.due(account.id, now)
                if self._batch_ready(job, now_utc, cache)
            ]
            if not due and not auto_pool:
                continue
            due_accounts += 1
            if not eligibility.inside_window(policy, moment):
                blocked_window += 1
                continue
            remaining = self._quota.available(account.id, day, policy.daily_allowance)
            if remaining <= 0:
                blocked_allowance += 1
                continue
            if time.monotonic() < self._next_allowed.get(account.id, 0.0):
                continue
            lanes = self._transports.lanes(account)
            if lanes <= 0:
                continue
            candidates.append(Candidate(account, due, remaining, lanes))
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
            self._log.debug(
                "job.leased",
                job=claimed.id,
                account=candidate.account.id,
            )
            picked.append((claimed, candidate.account))
            candidate.remaining -= 1
            policy = policies[candidate.account.id]
            per_account = sum(
                1 for _, account in picked if account.id == candidate.account.id
            )
            if (
                per_account >= min(policy.max_in_flight, candidate.lanes)
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
        self._apply_spacing(picked, policies)
        self._log_cycle(len(picked), sent, deferred, started)
        self._finalize({job.batch_id for job, _ in picked})
        if failed:
            self._log.debug("dispatch.failed", count=failed)

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

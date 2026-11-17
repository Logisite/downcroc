from __future__ import annotations

import asyncio
import random
import threading

from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.outbound.backfill.api_stage import ApiStage
from downcroc.core.outbound.backfill.consume import PageTurn
from downcroc.core.outbound.backfill.imap_stage import imap_sweep, lane_token
from downcroc.core.outbound.backfill.lanes import Lane, PassStats
from downcroc.core.outbound.backfill.plan import PassPlan, build_plan
from downcroc.domain.accounts import Account
from downcroc.domain.errors import VaultLocked
from downcroc.domain.providers import ProviderSpec
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.config.schema import BackfillSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.thread_backfill import HoleCounts, ThreadBackfillRepo

SHUTDOWN_JOIN_S = 10.0


class ThreadBackfillWorker:
    """Recovers Gmail provider thread ids for old sent mail, in the background.

    One asyncio task owns the lifecycle: passes, cooldowns, and idle re-checks.
    Blocking IMAP and API work runs in worker threads, at most ``max_accounts``
    account lanes at a time.
    """

    def __init__(
        self,
        settings: BackfillSettings,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        credentials: CredentialResolver,
        attempts: ThreadBackfillRepo,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._providers = providers
        self._credentials = credentials
        self._attempts = attempts
        self._bus = bus
        self._log = log
        self._stage = ApiStage(
            attempts,
            log,
            settle_s=settings.settle_s,
            retry_base_s=settings.retry_base_s,
            retry_max_s=settings.retry_max_s,
            retry_after_days=settings.retry_after_days,
        )
        self._turn = PageTurn(self._stage, log, settings.max_concurrency)
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._wake_reason = "vault_unlocked"
        self._sweeps: dict[str, dict[str, set[str]]] = {}
        self._sweep_lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None
        self._listen_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None or not self._settings.enabled:
            return
        self._stop.clear()
        self._wake.clear()
        self._task = asyncio.create_task(self._run())
        self._listen_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        listener, self._listen_task = self._listen_task, None
        if listener is not None:
            listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=SHUTDOWN_JOIN_S)
        except Exception:  # noqa: BLE001
            # Shutdown abandons a slow pass; per-row writes stay consistent.
            self._log.info(
                "backfill.backoff", account="", delay_s=0, cause="shutdown_join"
            )

    async def _listen(self) -> None:
        subscription = self._bus.subscribe()
        try:
            while not self._stop.is_set():
                event = await subscription.queue.get()
                if event is None:
                    return
                if event.type == "vault.unlocked":
                    self._wake_reason = "vault_unlocked"
                    self._wake.set()
                elif event.type in {"account.connected", "account.needs_reauth"}:
                    self._wake_reason = event.type.replace(".", "_")
                    self._wake.set()
        finally:
            self._bus.unsubscribe(subscription)

    async def _run(self) -> None:
        await self._wait(self._settings.startup_delay_s)
        while not self._stop.is_set():
            plan = self._plan()
            if plan.due == 0:
                self._log.info(
                    "backfill.idle_check",
                    holes=plan.holes,
                    due=0,
                    waiting=plan.waiting,
                    blocked=plan.blocked,
                    missing=plan.missing,
                    unresolved=plan.unresolved,
                    next_due_at=plan.next_due_at,
                )
                await self._wait(self._idle_wait(plan))
                continue
            try:
                await self._pass(plan)
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "backfill.backoff",
                    account="",
                    delay_s=self._settings.pass_cooldown_s,
                    cause=error.__class__.__name__,
                )
                await self._wait(self._settings.pass_cooldown_s)

    async def _pass(self, plan: PassPlan) -> None:
        self._log.info(
            "backfill.started",
            holes=plan.holes,
            accounts=len(plan.accounts),
            due=plan.due,
            waiting=plan.waiting,
            blocked=plan.blocked,
            missing=plan.missing,
            unresolved=plan.unresolved,
        )
        self._log.info(
            "backfill.pass_plan",
            due=plan.due,
            waiting=plan.waiting,
            blocked=plan.blocked,
            missing=plan.missing,
            unresolved=plan.unresolved,
            next_due_at=plan.next_due_at,
            blocked_accounts=[
                f"{item.account_id}:{item.reason}" for item in plan.blocked_accounts
            ],
        )
        totals = PassStats()
        while not self._stop.is_set():
            current = self._plan()
            if current.due == 0:
                self._finished(totals, current)
                return
            lanes = [
                Lane(account=item.account, spec=item.spec, counts=item.counts)
                for item in current.accounts
                if item.counts.due
            ]
            turn = await self._drain_lanes(lanes)
            totals.add(turn)
            current = self._plan()
            self._log.info(
                "backfill.pass_done",
                resolved=turn.resolved,
                missing=turn.missing,
                waiting=turn.waiting,
                unresolved=turn.unresolved,
                errors=turn.errors,
                due=current.due,
                next_waiting=current.waiting,
                blocked=current.blocked,
                left=current.left,
            )
            if current.due == 0:
                self._finished(totals, current)
                return
            if turn.progress:
                continue
            self._log.info(
                "backfill.cooldown",
                seconds=self._settings.pass_cooldown_s,
                left=current.left,
                due=current.due,
                reason=self._cooldown_reason(),
            )
            await self._wait(self._settings.pass_cooldown_s)

    def _finished(self, totals: PassStats, current: PassPlan) -> None:
        self._log.info(
            "backfill.finished",
            resolved=totals.resolved,
            missing=totals.missing,
            waiting=totals.waiting,
            unresolved=totals.unresolved,
            left=current.left,
            blocked=current.blocked,
            reason="drained",
        )

    async def _drain_lanes(self, lanes: list[Lane]) -> PassStats:
        for lane in lanes:
            lane.stats = PassStats()
        pending = list(lanes)
        totals = PassStats()
        while pending and not self._stop.is_set():
            batch, pending = (
                pending[: self._settings.max_accounts],
                pending[self._settings.max_accounts :],
            )
            results = await asyncio.gather(
                *(asyncio.to_thread(self._drain_account, lane) for lane in batch),
                return_exceptions=True,
            )
            for lane, result in zip(batch, results, strict=True):
                if isinstance(result, PassStats):
                    totals.add(result)
                else:
                    self._log.error(
                        "backfill.backoff",
                        account=lane.account.id,
                        delay_s=self._settings.pass_cooldown_s,
                        cause=type(result).__name__,
                    )
        return totals

    def _drain_account(self, lane: Lane) -> PassStats:
        """Blocking: drain one account completely, sweep first, API fallback next."""

        account, spec, stats = lane.account, lane.spec, lane.stats
        lane.counts = self._attempts.counts().get(
            account.id, HoleCounts(account_id=account.id)
        )
        self._log.info(
            "backfill.account_started",
            account=account.id,
            holes=lane.counts.open,
            due=lane.counts.due,
            waiting=lane.counts.waiting,
        )
        token = lane_token(account, spec, self._credentials, self._log)
        if token is None:
            return stats
        self._sweep(lane, token)
        while not self._stop.is_set():
            holes = self._attempts.due_holes(account.id, self._settings.page_size)
            if not holes or not self._turn.run(
                account, spec, token, holes, lane.sweep_threads, stats
            ):
                break
        return stats

    def _sweep(self, lane: Lane, token: str) -> None:
        """Run or reuse the per-run IMAP Sent sweep for this lane's account."""

        if lane.swept:
            return
        lane.swept = True
        account = lane.account
        with self._sweep_lock:
            cached = self._sweeps.get(account.id)
        if cached is not None:
            lane.sweep_threads = cached
            return
        if lane.counts.open < self._settings.imap_min_holes:
            return
        result = imap_sweep(
            account,
            lane.spec,
            token,
            chunk=self._settings.imap_chunk,
            pace_s=self._pace(),
            log=self._log,
        )
        if result is not None:
            lane.sweep_threads = result.threads
            with self._sweep_lock:
                self._sweeps[account.id] = result.threads

    def _plan(self) -> PassPlan:
        counts = self._attempts.counts()
        known = {account.id: account for account in self._accounts.list()}
        return build_plan(counts, known, self._spec, now=utc_now())

    def _spec(self, account: Account) -> ProviderSpec | None:
        try:
            return self._providers.get(account.provider)
        except KeyError:
            return None

    def _idle_wait(self, plan: PassPlan) -> float:
        delay = self._settings.recheck_s
        if plan.next_due_at is None:
            return delay
        try:
            seconds = (
                parse_utc(plan.next_due_at) - parse_utc(utc_now())
            ).total_seconds()
        except ValueError:
            return delay
        return min(delay, max(0.05, seconds))

    def _pace(self) -> float:
        low, high = self._settings.jitter_s, self._settings.jitter_max_s
        return random.uniform(low, max(low, high))

    def _cooldown_reason(self) -> str:
        try:
            self._credentials.ensure_unlocked()
        except VaultLocked:
            return "vault_locked"
        return "no_progress"

    async def _wait(self, seconds: float) -> None:
        if seconds <= 0:
            return
        waiters = {
            asyncio.create_task(self._stop.wait()),
            asyncio.create_task(self._wake.wait()),
        }
        woken = False
        try:
            await asyncio.wait(
                waiters,
                timeout=seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            woken = self._wake.is_set() and not self._stop.is_set()
        finally:
            for waiter in waiters:
                waiter.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
            self._wake.clear()
        if woken:
            self._log.info("backfill.resumed", reason=self._wake_reason)

from __future__ import annotations

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from downcroc.core.outbound.backfill.api_stage import ApiStage, Outcome
from downcroc.core.outbound.backfill.imap_stage import imap_sweep, lane_token
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.attempts import ThreadHole
from downcroc.domain.providers import ProviderSpec
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.config.schema import BackfillSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo

SHUTDOWN_JOIN_S = 10.0
STALL_LIMIT = 2


@dataclass
class PassStats:
    resolved: int = 0
    missing: int = 0

    @property
    def progress(self) -> int:
        return self.resolved + self.missing


@dataclass
class _Lane:
    """One account's drain turn inside a pass."""

    account: Account
    spec: ProviderSpec
    holes: int
    stats: PassStats = field(default_factory=PassStats)


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
        tokens: TokenManager,
        attempts: SendAttemptRepo,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._providers = providers
        self._tokens = tokens
        self._attempts = attempts
        self._log = log
        self._stage = ApiStage(
            attempts, log, retry_after_days=settings.retry_after_days
        )
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None or not self._settings.enabled:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
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

    async def _run(self) -> None:
        await self._wait(self._settings.startup_delay_s)
        while not self._stop.is_set():
            counts = self._attempts.thread_hole_counts()
            lanes = self._eligible(counts)
            if not lanes:
                self._log.info("backfill.idle_check", holes=sum(counts.values()))
                await self._wait(self._settings.recheck_s)
                continue
            try:
                await self._pass(lanes, holes=sum(counts.values()))
            except Exception as error:  # noqa: BLE001
                self._log.error(
                    "backfill.backoff",
                    account="",
                    delay_s=self._settings.pass_cooldown_s,
                    cause=error.__class__.__name__,
                )
                await self._wait(self._settings.pass_cooldown_s)

    async def _pass(self, lanes: list[_Lane], *, holes: int) -> None:
        self._log.info("backfill.started", holes=holes, accounts=len(lanes))
        stalled = 0
        while not self._stop.is_set():
            totals = await self._drain_lanes(lanes)
            remaining = sum(self._attempts.thread_hole_counts().values())
            self._log.info(
                "backfill.pass_done",
                resolved=totals.resolved,
                missing=totals.missing,
                left=remaining,
            )
            if remaining == 0 or totals.progress == 0:
                stalled += 1
                if remaining == 0 or stalled >= STALL_LIMIT:
                    self._log.info(
                        "backfill.finished",
                        resolved=totals.resolved,
                        missing=totals.missing,
                        left=remaining,
                    )
                    return
            else:
                stalled = 0
            await self._wait(self._settings.pass_cooldown_s)

    async def _drain_lanes(self, lanes: list[_Lane]) -> PassStats:
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
                    totals.resolved += result.resolved
                    totals.missing += result.missing
                else:
                    self._log.error(
                        "backfill.backoff",
                        account=lane.account.id,
                        delay_s=self._settings.pass_cooldown_s,
                        cause=type(result).__name__,
                    )
        return totals

    def _drain_account(self, lane: _Lane) -> PassStats:
        """Blocking: drain one account completely, sweep first, API fallback next."""

        account, spec, stats = lane.account, lane.spec, lane.stats
        self._log.info("backfill.account_started", account=account.id, holes=lane.holes)
        token = lane_token(account, spec, self._tokens, self._log)
        if token is None:
            return stats
        sweep_threads: dict[str, set[str]] | None = None
        if lane.holes >= self._settings.imap_min_holes:
            result = imap_sweep(
                account,
                spec,
                token,
                chunk=self._settings.imap_chunk,
                pace_s=self._pace(),
                log=self._log,
            )
            if result is not None:
                sweep_threads = result.threads
        while not self._stop.is_set():
            holes = self._attempts.thread_holes(account.id, self._settings.page_size)
            if not holes or not self._consume(
                account, spec, token, holes, sweep_threads, stats
            ):
                break
        return stats

    def _consume(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
        holes: list[ThreadHole],
        sweep_threads: dict[str, set[str]] | None,
        stats: PassStats,
    ) -> bool:
        """One page turn. Returns True when the account may have more work."""

        leftovers = []
        for hole in holes:
            candidates = (
                sweep_threads.get(hole.message_id)
                if sweep_threads is not None
                else None
            )
            if candidates is not None and len(candidates) == 1:
                if (
                    self._stage.write(
                        account, hole, next(iter(candidates)), medium="imap"
                    ).state
                    == "resolved"
                ):
                    stats.resolved += 1
                continue
            if candidates is not None and len(candidates) > 1:
                self._log.info("backfill.ambiguous", attempt=hole.attempt_id)
            leftovers.append(hole)
        progressed = False
        for outcome in self._resolve_page(account, spec, token, leftovers):
            if outcome.state == "resolved":
                stats.resolved += 1
                progressed = True
            elif outcome.state == "missing":
                stats.missing += 1
                progressed = True
            elif outcome.state in {"backoff", "skipped"} and not progressed:
                return False
        return progressed

    def _resolve_page(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
        holes: list[ThreadHole],
    ) -> list[Outcome]:
        if not holes:
            return []
        width = min(self._settings.max_concurrency, len(holes))
        if width <= 1:
            return [self._stage.resolve(account, spec, hole, token) for hole in holes]
        with ThreadPoolExecutor(max_workers=width) as pool:
            return list(
                pool.map(
                    lambda hole: self._stage.resolve(account, spec, hole, token),
                    holes,
                )
            )

    def _eligible(self, counts: dict[str, int]) -> list[_Lane]:
        known = {account.id: account for account in self._accounts.list()}
        lanes: list[_Lane] = []
        for account_id in sorted(counts):
            account = known.get(account_id)
            if account is None or account.status is not AccountStatus.CONNECTED:
                continue
            spec = self._spec(account)
            if spec is None or not spec.api_configured:
                continue
            lanes.append(_Lane(account=account, spec=spec, holes=counts[account_id]))
        return lanes

    def _spec(self, account: Account) -> ProviderSpec | None:
        try:
            return self._providers.get(account.provider)
        except KeyError:
            return None

    def _pace(self) -> float:
        low, high = self._settings.jitter_s, self._settings.jitter_max_s
        return random.uniform(low, max(low, high))

    async def _wait(self, seconds: float) -> None:
        if seconds <= 0:
            return
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

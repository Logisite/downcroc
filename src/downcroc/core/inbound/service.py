from __future__ import annotations

import queue
import threading
import time

from downcroc.core.events import EventBus
from downcroc.core.inbound.gmail_watcher import GmailWatcher
from downcroc.core.inbound.plan import health_rows, plan_for, select_event
from downcroc.core.inbound.signals import (
    STOP,
    SyncWaiter,
    WatcherEvent,
    WatcherHandle,
    WatcherState,
)
from downcroc.core.inbound.sources import choose_source
from downcroc.core.inbound.sweep import SweepScheduler
from downcroc.core.inbound.watcher import WatcherRunner
from downcroc.core.inbound.worker import QueueWorker
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.stats import StatsService
from downcroc.core.vault import VaultService
from downcroc.domain.accounts import AccountStatus
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import ConnectSettings, InboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo


class InboundService:
    def __init__(
        self,
        accounts: AccountRepo,
        messages: MessageRepo,
        stats: StatsService,
        registry: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        clients: OAuthClientService,
        content: ContentStore,
        bus: EventBus,
        log: EventLogger,
        settings: InboundSettings,
        connect: ConnectSettings,
        api_timeout_s: float,
        runtime: RuntimeStateRepo,
        connectivity: object | None = None,
    ) -> None:
        self._accounts = accounts
        self._stats = stats
        self._clients = clients
        self._connectivity = connectivity
        self._was_online = True
        self._log = log
        self._settings = settings
        self._initialized_at = runtime.get().initialized_at
        self._queue: queue.Queue[object] = queue.Queue()
        self._guard = threading.RLock()
        self._watchers: dict[str, WatcherHandle] = {}
        self._running = False
        self._closed = False
        self._opened = False
        self._wake = threading.Event()
        self._watcher = WatcherRunner(
            self._queue,
            self._guard,
            registry,
            vault,
            tokens,
            clients,
            log,
            settings,
            connect,
            self._initialized_at,
        )
        self._gmail = GmailWatcher(
            self._queue,
            self._guard,
            tokens,
            clients,
            messages,
            log,
            settings,
            api_timeout_s,
            self._initialized_at,
        )
        self._sweep = SweepScheduler(
            self._queue,
            tokens,
            clients,
            accounts,
            messages,
            log,
            settings,
            api_timeout_s,
            self._initialized_at,
        )
        self._sweep_thread: threading.Thread | None = None
        self._worker = QueueWorker(
            self._queue,
            accounts,
            messages,
            content,
            stats,
            bus,
            log,
            settings,
            self._initialized_at,
        )
        self._ingester = threading.Thread(
            target=self._worker.run,
            name="downcroc-ingest",
            daemon=True,
        )
        self._supervisor = threading.Thread(
            target=self._supervise,
            name="downcroc-watchdog",
            daemon=True,
        )

    def open(self) -> None:
        if self._opened:
            return
        self._opened = True
        self._ingester.start()
        self._supervisor.start()
        self._sweep_thread = self._sweep.start()

    def start_all(self) -> None:
        with self._guard:
            self._running = True
        self._wake.set()

    def stop_all(self, reason: str) -> None:
        with self._guard:
            self._running = False
            handles = list(self._watchers.values())
            self._watchers.clear()
        for handle in handles:
            self._stop(handle, reason)
        self._wake.set()

    def account_connected(self, account_id: str) -> None:
        with self._guard:
            handle = self._watchers.get(account_id)
            if handle is not None:
                handle.blocked = None
                handle.failures = 0
                handle.next_start = 0.0
        self._wake.set()

    def account_removed(self, account_id: str) -> None:
        with self._guard:
            handle = self._watchers.pop(account_id, None)
        if handle is not None:
            self._stop(handle, "account_removed")

    def account_changed(self, account_id: str, enabled: bool) -> None:
        if enabled:
            self.account_connected(account_id)
            return
        with self._guard:
            handle = self._watchers.pop(account_id, None)
        if handle is not None:
            self._stop(handle, "watcher_disabled")

    def sync_now(self, account_id: str) -> None:
        with self._guard:
            handle = self._watchers.get(account_id)
            if handle is not None:
                handle.blocked = None
                handle.failures = 0
                handle.next_start = 0.0
                if handle.thread is not None and handle.thread.is_alive():
                    handle.refresh.set()
                    return
        self._wake.set()

    def sync_wait(self, account_id: str, timeout_s: float) -> tuple[bool, str]:
        with self._guard:
            handle = self._watchers.get(account_id)
            if handle is None:
                return False, "watcher_unavailable"
            if handle.blocked is not None:
                return False, handle.blocked
            waiter = SyncWaiter()
            handle.sync_waiters.append(waiter)
            handle.next_start = 0.0
            if handle.thread is not None and handle.thread.is_alive():
                handle.refresh.set()
            else:
                self._wake.set()
        try:
            if not waiter.done.wait(timeout_s):
                return False, "timeout"
        finally:
            with self._guard:
                if waiter in handle.sync_waiters:
                    handle.sync_waiters.remove(waiter)
        return waiter.ok, waiter.reason

    def close(self) -> None:
        if self._closed:
            return
        self.stop_all("shutdown")
        self._closed = True
        self._sweep.stop()
        self._wake.set()
        if self._opened:
            self._queue.put(STOP)
            self._supervisor.join(timeout=self._settings.shutdown_join_s)
            if self._sweep_thread is not None:
                self._sweep_thread.join(timeout=self._settings.shutdown_join_s)
            self._ingester.join(timeout=self._settings.shutdown_join_s)

    def _supervise(self) -> None:
        while not self._closed:
            self._wake.wait(timeout=0.5)
            self._wake.clear()
            if self._closed:
                return
            try:
                self._reconcile()
            except Exception as error:  # noqa: BLE001 - the supervisor must survive
                self._log.error(
                    "watcher.supervisor_failed",
                    error=type(error).__name__,
                    detail=str(error),
                )

    def _reconcile(self) -> None:
        if not self._running:
            return
        if self._connectivity is not None and not self._connectivity.online:
            if self._was_online:
                self._was_online = False
                self._log.info("watcher.paused", reason="connectivity")
            return
        if not self._was_online:
            self._was_online = True
            self._log.info("watcher.resumed", reason="connectivity")
        accounts = {account.id: account for account in self._accounts.list()}
        with self._guard:
            handles = dict(self._watchers)
        for account_id, handle in handles.items():
            account = accounts.get(account_id)
            if (
                account is None
                or account.status is not AccountStatus.CONNECTED
                or not account.watcher_enabled
            ):
                with self._guard:
                    self._watchers.pop(account_id, None)
                self._stop(handle, "account_not_connected")
        now = time.monotonic()
        for account_id, account in accounts.items():
            if (
                account.status is not AccountStatus.CONNECTED
                or not account.watcher_enabled
            ):
                continue
            spec = self._clients.spec_for_account(account)
            with self._guard:
                handle = self._watchers.get(account_id)
                previous = handle.source if handle is not None else None
                if handle is not None and handle.source == "imap":
                    allow_idle = handle.allow_idle
                    denied = False
                    choice = choose_source(
                        account,
                        spec,
                        self._settings.source,
                        allow_idle=allow_idle,
                    )
                else:
                    choice, allow_idle, denied = plan_for(
                        self._settings,
                        account,
                        spec,
                        self._watchers,
                    )
                if denied:
                    self._idle_cap(account)
                if handle is not None and handle.source != choice.source:
                    self._watchers.pop(account_id, None)
                    self._stop(handle, "source_switch")
                    handle = None
                if handle is None:
                    handle = WatcherHandle(
                        account=account,
                        source=choice.source,
                        allow_idle=allow_idle,
                    )
                    handle.mode = choice.mode
                    self._watchers[account_id] = handle
                    self._select(account, choice.source, previous, spec)
                    handle.account = self._accounts.get(account.id)
                else:
                    handle.account = account
                if handle.blocked is not None:
                    continue
                if handle.next_start > now:
                    continue
                if handle.thread is not None and handle.thread.is_alive():
                    continue
                if handle.thread is not None and handle.next_start == 0.0:
                    self._record_died(handle)
                if handle.stop.is_set():
                    continue
                target = (
                    self._gmail.run
                    if handle.source == "gmail_api"
                    else self._watcher.run
                )
                handle.thread = threading.Thread(
                    target=target,
                    args=(handle,),
                    name=f"downcroc-watch-{account_id}",
                    daemon=True,
                )
                handle.thread.start()

    def _idle_cap(self, account) -> None:
        cap = max(1, int(self._settings.idle_fleet_cap))
        self._log.info(
            "inbound.idle_cap",
            account=account.id,
            cap=cap,
            fallback="imap_poll",
        )
        self._queue.put(
            WatcherEvent(
                "inbound.idle_cap",
                {"account": account.id, "cap": cap, "fallback": "imap_poll"},
            )
        )

    def _select(self, account, source: str, previous: str | None, spec) -> None:
        if previous == source:
            return
        self._accounts.set_inbound_source(account.id, source, utc_now())
        if source == "imap" and account.cursor_source == "gmail_api":
            self._accounts.reset_cursor(account.id, 0)
        event, fields = select_event(account, source, self._settings.source)
        if event == "inbound.source_switch" and source == "gmail_api":
            self._log.info(event, **fields)
            return
        self._log.info(event, **fields)
        self._queue.put(WatcherEvent(event, fields))

    def health(self) -> list[dict[str, object]]:
        with self._guard:
            handles = dict(self._watchers)
        return health_rows(self._accounts.list(), handles)

    def _record_died(self, handle: WatcherHandle) -> None:
        handle.failures += 1
        retry = self._watcher.retry_in(handle.failures)
        handle.next_start = time.monotonic() + retry
        self._queue.put(
            WatcherState(
                account_id=handle.account.id,
                ok=False,
                reason="watcher_died",
                retry_in_s=retry,
                source=handle.source,
                mode=handle.mode,
            )
        )
        self._log.warning(
            "watcher.stopped",
            account=handle.account.id,
            reason="watcher_died",
            retry_in_s=retry,
        )

    def _stop(self, handle: WatcherHandle, reason: str) -> None:
        handle.stop_reason = reason
        handle.stop.set()
        handle.refresh.set()
        thread = handle.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._settings.shutdown_join_s)

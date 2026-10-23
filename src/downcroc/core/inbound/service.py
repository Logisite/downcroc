from __future__ import annotations

import queue
import threading
import time

from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.events import EventBus
from downcroc.core.inbound.signals import (
    STOP,
    WatcherHandle,
    WatcherState,
)
from downcroc.core.inbound.watcher import WatcherRunner
from downcroc.core.inbound.worker import QueueWorker
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import AccountStatus
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.config.schema import ConnectSettings, InboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import MessageRepo


class InboundService:
    def __init__(
        self,
        accounts: AccountRepo,
        messages: MessageRepo,
        registry: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        content: ContentStore,
        bus: EventBus,
        log: EventLogger,
        settings: InboundSettings,
        connect: ConnectSettings,
    ) -> None:
        self._accounts = accounts
        self._log = log
        self._settings = settings
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
            log,
            settings,
            connect,
        )
        self._worker = QueueWorker(
            self._queue,
            accounts,
            messages,
            content,
            bus,
            log,
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

    def close(self) -> None:
        if self._closed:
            return
        self.stop_all("shutdown")
        self._closed = True
        self._wake.set()
        if self._opened:
            self._queue.put(STOP)
            self._supervisor.join(timeout=self._settings.shutdown_join_s)
            self._ingester.join(timeout=self._settings.shutdown_join_s)

    def _supervise(self) -> None:
        while not self._closed:
            self._wake.wait(timeout=0.5)
            self._wake.clear()
            if self._closed:
                return
            try:
                self._reconcile()
            except (SQLAlchemyError, OSError, RuntimeError) as error:
                self._log.error("watcher.supervisor_failed", error=str(error))

    def _reconcile(self) -> None:
        if not self._running:
            return
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
            with self._guard:
                handle = self._watchers.get(account_id)
                if handle is None:
                    handle = WatcherHandle(account=account)
                    self._watchers[account_id] = handle
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
                handle.thread = threading.Thread(
                    target=self._watcher.run,
                    args=(handle,),
                    name=f"downcroc-watch-{account_id}",
                    daemon=True,
                )
                handle.thread.start()

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

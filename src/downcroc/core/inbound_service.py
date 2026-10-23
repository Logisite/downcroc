from __future__ import annotations

import imaplib
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from imap_tools.errors import ImapToolsError
from sqlalchemy.exc import SQLAlchemyError

from downcroc.core.events import EventBus
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import (
    AccountNotFound,
    OAuthNotConfigured,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.messages import PreparedAttachment
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.mail.imap import client as imap
from downcroc.mail.imap import connection
from downcroc.mail.imap.parse import parse_message
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import ConnectSettings, InboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import IngestResult, MessageRepo

FOLDER = "INBOX"
STOP = object()


@dataclass
class _IngestJob:
    account_id: str
    incoming: Any
    done: threading.Event = field(default_factory=threading.Event)
    result: IngestResult | None = None
    error: BaseException | None = None


@dataclass
class _CursorJob:
    account_id: str
    uidvalidity: int
    last_uid: int
    reset: bool
    done: threading.Event = field(default_factory=threading.Event)
    error: BaseException | None = None


@dataclass(frozen=True)
class _WatcherState:
    account_id: str
    ok: bool
    host: str = ""
    uidvalidity: int = 0
    reason: str = ""
    retry_in_s: int = 0
    needs_reauth: bool = False


@dataclass(frozen=True)
class _WatcherEvent:
    event: str
    data: dict[str, Any]


@dataclass
class _WatcherHandle:
    account: Account
    stop: threading.Event = field(default_factory=threading.Event)
    refresh: threading.Event = field(default_factory=threading.Event)
    failures: int = 0
    next_start: float = 0.0
    blocked: str | None = None
    stop_reason: str | None = None
    thread: threading.Thread | None = None


class _Stopped(Exception):
    pass


class _WatchFailure(Exception):
    def __init__(
        self,
        reason: str,
        *,
        needs_reauth: bool = False,
        fatal: bool = False,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.needs_reauth = needs_reauth
        self.fatal = fatal


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
        self._messages = messages
        self._registry = registry
        self._vault = vault
        self._tokens = tokens
        self._content = content
        self._bus = bus
        self._log = log
        self._settings = settings
        self._connect_settings = connect
        self._queue: queue.Queue[object] = queue.Queue()
        self._guard = threading.RLock()
        self._watchers: dict[str, _WatcherHandle] = {}
        self._running = False
        self._closed = False
        self._opened = False
        self._wake = threading.Event()
        self._ingester = threading.Thread(
            target=self._ingest_loop,
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
                    handle = _WatcherHandle(account=account)
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
                    target=self._run_watcher,
                    args=(handle,),
                    name=f"downcroc-watch-{account_id}",
                    daemon=True,
                )
                handle.thread.start()

    def _record_died(self, handle: _WatcherHandle) -> None:
        handle.failures += 1
        retry = self._retry_in(handle.failures)
        handle.next_start = time.monotonic() + retry
        self._queue.put(
            _WatcherState(
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

    def _stop(self, handle: _WatcherHandle, reason: str) -> None:
        handle.stop_reason = reason
        handle.stop.set()
        handle.refresh.set()
        thread = handle.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._settings.shutdown_join_s)

    def _run_watcher(self, handle: _WatcherHandle) -> None:
        failure: _WatchFailure | None = None
        try:
            self._watch(handle)
        except _Stopped:
            pass
        except _WatchFailure as error:
            failure = error
        except NeedsReauth as error:
            failure = _WatchFailure(error.reason, needs_reauth=True)
        except VaultSecretMissing:
            failure = _WatchFailure("credential_missing", needs_reauth=True)
        except VaultLocked:
            failure = _WatchFailure("vault_locked", fatal=True)
        except TokenRefreshUnavailable:
            failure = _WatchFailure("oauth_unavailable")
        except TokenRefreshFailed:
            failure = _WatchFailure("oauth_failed")
        except OAuthNotConfigured:
            failure = _WatchFailure("oauth_not_configured", fatal=True)
        except connection.ImapAuthError:
            failure = _WatchFailure("imap_auth_failed", needs_reauth=True)
        except connection.ImapTlsError:
            failure = _WatchFailure("imap_tls_failed")
        except connection.ImapNetworkError:
            failure = _WatchFailure("imap_unreachable")
        except connection.ImapProtocolError:
            failure = _WatchFailure("imap_protocol_error")
        except Exception as error:  # noqa: BLE001
            failure = _WatchFailure("watcher_error")
            self._log.error(
                "watcher.error", account=handle.account.id, error=str(error)
            )

        reason = handle.stop_reason or "watcher_stopped"
        retry = 0
        if failure is not None:
            reason = failure.reason
            if failure.needs_reauth or failure.fatal:
                with self._guard:
                    handle.blocked = reason
            retry = self._retry_after(handle, failure)
            self._queue.put(
                _WatcherState(
                    account_id=handle.account.id,
                    ok=False,
                    reason=reason,
                    retry_in_s=retry,
                    needs_reauth=failure.needs_reauth,
                )
            )
        else:
            account_id = handle.account.id
            self._queue.put(
                _WatcherEvent(
                    "watcher.stopped",
                    {
                        "account": account_id,
                        "reason": reason,
                        "retry_in_s": 0,
                    },
                )
            )
        self._log.warning(
            "watcher.stopped",
            account=handle.account.id,
            reason=reason,
            retry_in_s=retry,
        )

    def _retry_after(self, handle: _WatcherHandle, failure: _WatchFailure) -> int:
        if failure.needs_reauth or failure.fatal:
            with self._guard:
                handle.failures = 0
                handle.next_start = 0.0
            return 0
        with self._guard:
            handle.failures += 1
            retry = self._retry_in(handle.failures)
            handle.next_start = time.monotonic() + retry
        return retry

    def _retry_in(self, failures: int) -> int:
        backoff = self._settings.backoff_s
        return backoff[min(max(failures - 1, 0), len(backoff) - 1)]

    def _watch(self, handle: _WatcherHandle) -> None:
        account = handle.account
        spec = self._registry.get(account.provider)
        box = self._connect(spec, account)
        try:
            state = imap.select_inbox(box)
            self._log.info(
                "watcher.started",
                account=account.id,
                host=spec.imap_host,
                uidvalidity=state.uidvalidity,
            )
            with self._guard:
                handle.failures = 0
                handle.next_start = 0.0
                handle.blocked = None
            self._queue.put(
                _WatcherState(
                    account_id=account.id,
                    ok=True,
                    host=spec.imap_host,
                    uidvalidity=state.uidvalidity,
                )
            )
            uidvalidity = account.uidvalidity
            last_uid = account.last_uid
            while not handle.stop.is_set():
                uidvalidity, last_uid = self._sync(
                    handle,
                    box,
                    account,
                    state,
                    uidvalidity,
                    last_uid,
                )
                if handle.stop.is_set():
                    break
                if spec.supports_idle:
                    self._idle_loop(handle, box, account)
                else:
                    self._poll_loop(handle, account)
                if not handle.stop.is_set():
                    state = imap.select_inbox(box)
        finally:
            imap.close(box)

    def _connect(self, spec: ProviderSpec, account: Account):
        password: str | None = None
        access_token: str | None = None
        if spec.auth_kind is AuthKind.OAUTH2:
            access_token = self._tokens.access_token(account)
        elif spec.auth_kind is AuthKind.APP_PASSWORD:
            if account.credential_key is None:
                raise VaultSecretMissing("the account has no credential")
            password = self._vault.get_secret(account.credential_key).value
        else:
            raise _WatchFailure("provider_not_configured", fatal=True)
        box = connection.connect(spec, self._connect_settings.imap_timeout_s)
        try:
            connection.authenticate(
                box,
                account.address,
                password=password,
                access_token=access_token,
            )
        except Exception:
            imap.close(box)
            raise
        return box

    def _sync(
        self,
        handle: _WatcherHandle,
        box,
        account: Account,
        state: imap.InboxState,
        uidvalidity: int,
        last_uid: int,
    ) -> tuple[int, int]:
        initial = False
        resync = False
        if uidvalidity == 0:
            initial = True
        elif uidvalidity != state.uidvalidity:
            self._cursor(
                handle,
                state.uidvalidity,
                0,
                reset=True,
            )
            uidvalidity = state.uidvalidity
            last_uid = 0
            resync = True
        if initial:
            uids = imap.search_initial(
                box,
                self._settings.initial_sync_days,
                self._settings.initial_sync_limit,
            )
        elif resync:
            uids = imap.search_all(box)
        else:
            uids = imap.search_new(box, last_uid)

        started = time.monotonic()
        count = 0
        highest = last_uid
        for message in imap.fetch_messages(box, uids, self._settings.fetch_batch):
            if handle.stop.is_set():
                raise _Stopped
            incoming = parse_message(
                message,
                state.uidvalidity,
                self._settings.body_max_bytes,
            )
            if incoming.uid <= 0:
                continue
            job = _IngestJob(account_id=account.id, incoming=incoming)
            self._queue.put(job)
            self._await(job, handle, "ingest_failed")
            highest = max(highest, incoming.uid)
            count += 1
        if initial or resync:
            baseline = max(highest, state.uidnext - 1)
            self._cursor(
                handle,
                state.uidvalidity,
                baseline,
                reset=False,
            )
            highest = baseline
        duration = round((time.monotonic() - started) * 1000)
        self._log.info(
            "imap.fetch",
            account=account.id,
            count=count,
            duration_ms=duration,
        )
        self._queue.put(
            _WatcherEvent(
                "imap.fetch",
                {
                    "account": account.id,
                    "count": count,
                    "duration_ms": duration,
                },
            )
        )
        return state.uidvalidity, highest

    def _cursor(
        self,
        handle: _WatcherHandle,
        uidvalidity: int,
        last_uid: int,
        *,
        reset: bool,
    ) -> None:
        job = _CursorJob(
            account_id=handle.account.id,
            uidvalidity=uidvalidity,
            last_uid=last_uid,
            reset=reset,
        )
        self._queue.put(job)
        if not self._wait(job.done, handle):
            raise _Stopped
        if job.error is not None:
            raise _WatchFailure("cursor_failed")

    def _await(self, job: _IngestJob, handle: _WatcherHandle, reason: str) -> None:
        if not self._wait(job.done, handle):
            raise _Stopped
        if job.error is not None:
            raise _WatchFailure(reason)

    def _wait(self, done: threading.Event, handle: _WatcherHandle) -> bool:
        deadline = time.monotonic() + self._settings.ingest_timeout_s
        while not done.wait(0.2):
            if handle.stop.is_set():
                return False
            if time.monotonic() >= deadline:
                raise _WatchFailure("ingest_timeout")
        return True

    def _idle_loop(self, handle: _WatcherHandle, box, account: Account) -> None:
        while not handle.stop.is_set():
            try:
                box.idle.start()
                started = time.monotonic()
                reason: str | None = None
                try:
                    while not handle.stop.is_set():
                        if handle.refresh.is_set():
                            handle.refresh.clear()
                            reason = "refresh"
                            break
                        remaining = self._settings.idle_timeout_s - (
                            time.monotonic() - started
                        )
                        if remaining <= 0:
                            reason = "timeout"
                            break
                        responses = box.idle.poll(timeout=min(1.0, remaining))
                        if responses:
                            joined = b" ".join(responses).upper()
                            reason = "exists" if b"EXISTS" in joined else "change"
                            break
                finally:
                    try:
                        box.idle.stop()
                    except imaplib.IMAP4.error, OSError, ImapToolsError:
                        pass
            except (imaplib.IMAP4.error, OSError, ImapToolsError) as error:
                raise _WatchFailure("imap_protocol_error") from error
            if reason is None:
                return
            self._wake_log(account.id, reason)
            return

    def _poll_loop(self, handle: _WatcherHandle, account: Account) -> None:
        deadline = time.monotonic() + self._settings.poll_interval_s
        while not handle.stop.is_set():
            if handle.refresh.is_set():
                handle.refresh.clear()
                self._wake_log(account.id, "refresh")
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._wake_log(account.id, "poll")
                return
            handle.stop.wait(timeout=min(1.0, remaining))

    def _wake_log(self, account_id: str, reason: str) -> None:
        self._log.info("watcher.idle_wake", account=account_id, reason=reason)
        self._queue.put(
            _WatcherEvent(
                "watcher.idle_wake",
                {"account": account_id, "reason": reason},
            )
        )

    def _ingest_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is STOP:
                    return
                if isinstance(item, _IngestJob):
                    self._handle_ingest(item)
                elif isinstance(item, _CursorJob):
                    self._handle_cursor(item)
                elif isinstance(item, _WatcherState):
                    self._handle_state(item)
                elif isinstance(item, _WatcherEvent):
                    self._bus.publish(item.event, item.data)
            except Exception as error:  # noqa: BLE001
                if isinstance(item, (_IngestJob, _CursorJob)):
                    item.error = error
                self._log.error(
                    "inbound.worker_failed",
                    error=str(error),
                    kind=type(item).__name__,
                )
            finally:
                if isinstance(item, (_IngestJob, _CursorJob)):
                    item.done.set()
                self._queue.task_done()

    def _handle_ingest(self, job: _IngestJob) -> None:
        incoming = job.incoming
        existing = self._messages.find_existing(
            job.account_id,
            FOLDER,
            incoming.uidvalidity,
            incoming.uid,
            incoming.message_id,
        )
        if existing is not None:
            self._messages.advance_cursor(
                job.account_id,
                incoming.uidvalidity,
                incoming.uid,
                utc_now(),
            )
            job.result = existing
            return
        prepared: list[PreparedAttachment] = []
        message_id = new_id("msg")
        for index, attachment in enumerate(incoming.attachments, start=1):
            stored = self._content.put_attachment(
                job.account_id,
                message_id,
                index,
                attachment.filename,
                attachment.payload,
            )
            prepared.append(
                PreparedAttachment(
                    id=new_id("att"),
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=stored.size,
                    path=stored.path,
                    hash=stored.hash,
                    inline=attachment.inline,
                    content_id=attachment.content_id,
                )
            )
        result = self._messages.ingest(
            job.account_id,
            FOLDER,
            incoming,
            tuple(prepared),
            message_id=message_id,
        )
        job.result = result
        self._log.info(
            "message.ingested",
            message_id=result.message_id,
            uid=incoming.uid,
            thread=result.thread_id,
            account=job.account_id,
        )
        self._bus.publish(
            "message.ingested",
            {
                "message_id": result.message_id,
                "uid": incoming.uid,
                "thread": result.thread_id,
                "account": job.account_id,
            },
        )
        for attachment in prepared:
            self._log.info(
                "attachment.stored",
                filename=attachment.filename,
                bytes=attachment.size,
                sha256=attachment.hash[:12],
                account=job.account_id,
                message_id=result.message_id,
            )
            self._bus.publish(
                "attachment.stored",
                {
                    "filename": attachment.filename,
                    "bytes": attachment.size,
                    "sha256": attachment.hash[:12],
                    "account": job.account_id,
                    "message_id": result.message_id,
                },
            )

    def _handle_cursor(self, job: _CursorJob) -> None:
        if job.reset:
            self._accounts.reset_cursor(job.account_id, job.uidvalidity)
        else:
            self._accounts.set_baseline(
                job.account_id,
                job.uidvalidity,
                job.last_uid,
                utc_now(),
            )

    def _handle_state(self, state: _WatcherState) -> None:
        if state.ok:
            self._accounts.watcher_succeeded(state.account_id, utc_now())
            self._bus.publish(
                "watcher.started",
                {
                    "account": state.account_id,
                    "host": state.host,
                    "uidvalidity": state.uidvalidity,
                },
            )
            return
        self._accounts.watcher_failed(state.account_id, state.reason)
        if state.needs_reauth:
            try:
                self._accounts.mark_needs_reauth(state.account_id, state.reason)
            except AccountNotFound:
                return
            self._bus.publish(
                "account.needs_reauth",
                {"id": state.account_id, "reason": state.reason},
            )
            self._log.warning(
                "account.needs_reauth",
                account=state.account_id,
                reason=state.reason,
            )
        self._bus.publish(
            "watcher.stopped",
            {
                "account": state.account_id,
                "reason": state.reason,
                "retry_in_s": state.retry_in_s,
            },
        )

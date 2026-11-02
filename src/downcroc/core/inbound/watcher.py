from __future__ import annotations

import queue
import threading
import time

from downcroc.core.inbound.idle import IdleLoops
from downcroc.core.inbound.signals import (
    CursorJob,
    IngestJob,
    Stopped,
    WatcherEvent,
    WatcherHandle,
    WatcherState,
    WatchFailure,
)
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import OAuthNotConfigured, VaultLocked, VaultSecretMissing
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
from downcroc.runtime.config.schema import ConnectSettings, InboundSettings
from downcroc.runtime.logging.setup import EventLogger


class WatcherRunner:
    def __init__(
        self,
        queue_: queue.Queue[object],
        guard: threading.RLock,
        registry: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        clients: OAuthClientService,
        log: EventLogger,
        settings: InboundSettings,
        connect: ConnectSettings,
    ) -> None:
        self._queue = queue_
        self._guard = guard
        self._registry = registry
        self._vault = vault
        self._tokens = tokens
        self._clients = clients
        self._log = log
        self._settings = settings
        self._connect_settings = connect
        self._loops = IdleLoops(queue_, log, settings)

    def retry_in(self, failures: int) -> int:
        backoff = self._settings.backoff_s
        return backoff[min(max(failures - 1, 0), len(backoff) - 1)]

    def run(self, handle: WatcherHandle) -> None:
        failure: WatchFailure | None = None
        try:
            self._watch(handle)
        except Stopped:
            pass
        except WatchFailure as error:
            failure = error
        except NeedsReauth as error:
            failure = WatchFailure(error.reason, needs_reauth=True)
        except VaultSecretMissing:
            failure = WatchFailure("credential_missing", needs_reauth=True)
        except VaultLocked:
            failure = WatchFailure("vault_locked", fatal=True)
        except TokenRefreshUnavailable:
            failure = WatchFailure("oauth_unavailable")
        except TokenRefreshFailed:
            failure = WatchFailure("oauth_failed")
        except OAuthNotConfigured:
            failure = WatchFailure("oauth_not_configured", fatal=True)
        except connection.ImapAuthError:
            failure = WatchFailure("imap_auth_failed", needs_reauth=True)
        except connection.ImapTlsError:
            failure = WatchFailure("imap_tls_failed")
        except connection.ImapNetworkError:
            failure = WatchFailure("imap_unreachable")
        except connection.ImapProtocolError:
            failure = WatchFailure("imap_protocol_error")
        except Exception as error:  # noqa: BLE001
            failure = WatchFailure("watcher_error")
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
                WatcherState(
                    account_id=handle.account.id,
                    ok=False,
                    reason=reason,
                    retry_in_s=retry,
                    needs_reauth=failure.needs_reauth,
                    source="imap",
                    mode=handle.mode,
                )
            )
        else:
            account_id = handle.account.id
            self._queue.put(
                WatcherEvent(
                    "watcher.stopped",
                    {
                        "account": account_id,
                        "reason": reason,
                        "retry_in_s": 0,
                    },
                )
            )
        self._notify_sync(handle, ok=False, reason=reason)
        self._log.warning(
            "watcher.stopped",
            account=handle.account.id,
            reason=reason,
            retry_in_s=retry,
        )

    def _notify_sync(
        self, handle: WatcherHandle, *, ok: bool, reason: str = ""
    ) -> None:
        with self._guard:
            waiters = list(handle.sync_waiters)
            handle.sync_waiters.clear()
        for waiter in waiters:
            waiter.ok = ok
            waiter.reason = reason
            waiter.done.set()

    def _retry_after(self, handle: WatcherHandle, failure: WatchFailure) -> int:
        if failure.needs_reauth or failure.fatal:
            with self._guard:
                handle.failures = 0
                handle.next_start = 0.0
            return 0
        with self._guard:
            handle.failures += 1
            retry = self.retry_in(handle.failures)
            handle.next_start = time.monotonic() + retry
        return retry

    def _watch(self, handle: WatcherHandle) -> None:
        account = handle.account
        spec = self._clients.spec_for_account(account)
        box = self._connect(spec, account)
        idle = spec.supports_idle and handle.allow_idle
        handle.mode = "idle" if idle else "imap_poll"
        try:
            state = imap.select_inbox(box)
            self._log.info(
                "watcher.started",
                account=account.id,
                host=spec.imap_host,
                uidvalidity=state.uidvalidity,
                mode=handle.mode,
            )
            with self._guard:
                handle.failures = 0
                handle.next_start = 0.0
                handle.blocked = None
            self._queue.put(
                WatcherState(
                    account_id=account.id,
                    ok=True,
                    host=spec.imap_host,
                    uidvalidity=state.uidvalidity,
                    source="imap",
                    mode=handle.mode,
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
                self._notify_sync(handle, ok=True)
                handle.mode = "idle" if idle else "imap_poll"
                if handle.stop.is_set():
                    break
                if idle:
                    self._loops.idle(handle, box, account)
                else:
                    self._loops.poll(handle, account)
                if not handle.stop.is_set():
                    handle.mode = "reconnecting"
                    state = imap.select_inbox(box)
        finally:
            imap.close(box)

    def _connect(self, spec: ProviderSpec, account: Account):
        password: str | None = None
        access_token: str | None = None
        if spec.auth_kind is AuthKind.OAUTH2:
            access_token = self._tokens.access_token(account, spec=spec)
        elif spec.auth_kind is AuthKind.APP_PASSWORD:
            if account.credential_key is None:
                raise VaultSecretMissing("the account has no credential")
            password = self._vault.get_secret(account.credential_key).value
        else:
            raise WatchFailure("provider_not_configured", fatal=True)
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
        handle: WatcherHandle,
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
                raise Stopped
            incoming = parse_message(
                message,
                state.uidvalidity,
                self._settings.body_max_bytes,
            )
            if incoming.uid <= 0:
                continue
            job = IngestJob(account_id=account.id, incoming=incoming)
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
            WatcherEvent(
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
        handle: WatcherHandle,
        uidvalidity: int,
        last_uid: int,
        *,
        reset: bool,
    ) -> None:
        job = CursorJob(
            account_id=handle.account.id,
            uidvalidity=uidvalidity,
            last_uid=last_uid,
            reset=reset,
        )
        self._queue.put(job)
        if not self._wait(job.done, handle):
            raise Stopped
        if job.error is not None:
            raise WatchFailure("cursor_failed")

    def _await(self, job: IngestJob, handle: WatcherHandle, reason: str) -> None:
        if not self._wait(job.done, handle):
            raise Stopped
        if job.error is not None:
            raise WatchFailure(reason)

    def _wait(self, done: threading.Event, handle: WatcherHandle) -> bool:
        deadline = time.monotonic() + self._settings.ingest_timeout_s
        while not done.wait(0.2):
            if handle.stop.is_set():
                return False
            if time.monotonic() >= deadline:
                raise WatchFailure("ingest_timeout")
        return True

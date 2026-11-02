from __future__ import annotations

import queue
import random
import threading
import time

from downcroc.core.inbound.gmail_ingest import (
    enqueue_ingest,
    fetch_incoming,
    wait_done,
)
from downcroc.core.inbound.gmail_target import project_id
from downcroc.core.inbound.signals import (
    HistoryJob,
    Stopped,
    WatcherEvent,
    WatcherHandle,
    WatcherState,
    WatchFailure,
)
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import OAuthNotConfigured, VaultLocked, VaultSecretMissing
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.gmail.read import (
    GmailMessageRef,
    backfill_refs,
    history,
)
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import InboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.messages import MessageRepo

LABELS = ("INBOX", "SENT")


class GmailWatcher:
    """One owner for an account that explicitly uses the Gmail API."""

    def __init__(
        self,
        queue_: queue.Queue[object],
        guard: threading.RLock,
        tokens: TokenManager,
        clients: OAuthClientService,
        messages: MessageRepo,
        log: EventLogger,
        settings: InboundSettings,
        api_timeout_s: float,
    ) -> None:
        self._queue = queue_
        self._guard = guard
        self._tokens = tokens
        self._clients = clients
        self._messages = messages
        self._log = log
        self._settings = settings
        self._api_timeout_s = api_timeout_s

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
        except gmail_api.GmailApiFailure as error:
            failure = self._api_failure(error)
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
                    source="gmail_api",
                    mode=handle.mode,
                    project_id=getattr(failure, "project_id", None),
                )
            )
        self._notify_sync(handle, ok=False, reason=reason)
        self._log.warning(
            "watcher.stopped",
            account=handle.account.id,
            reason=reason,
            source="gmail_api",
            retry_in_s=retry,
        )

    def _watch(self, handle: WatcherHandle) -> None:
        account = handle.account
        spec = self._clients.spec_for_account(account)
        handle.mode = "api_poll"
        token = self._tokens.access_token(account, spec=spec)
        history_id = (
            account.history_id if account.cursor_source == "gmail_api" else None
        )
        if history_id is None:
            history_id = self._full_sync(handle, account, spec, token, switch=True)
        self._state_ok(handle, account)
        while not handle.stop.is_set():
            if not self._sleep(handle):
                break
            try:
                history_id = self._incremental(handle, account, spec, token, history_id)
            except gmail_api.GmailApiFailure as error:
                if error.code != "gmail_history_expired":
                    raise
                self._log.warning(
                    "gmail.history_expired",
                    account=account.id,
                )
                history_id = self._full_sync(handle, account, spec, token)
                self._queue.put(
                    WatcherEvent(
                        "gmail.history_expired",
                        {"account": account.id, "resynced": True},
                    )
                )
            self._notify_sync(handle, ok=True)
        raise Stopped

    def _incremental(
        self,
        handle: WatcherHandle,
        account: Account,
        spec: ProviderSpec,
        token: str,
        history_id: str,
    ) -> str:
        refs: dict[str, GmailMessageRef] = {}
        latest = history_id
        for label in LABELS:
            page: str | None = None
            while True:
                found = history(
                    spec,
                    token,
                    history_id,
                    timeout_s=self._api_timeout_s,
                    page_token=page,
                    label_id=label,
                    project_id=project_id(self._clients, account),
                )
                if found.history_id:
                    latest = found.history_id
                for ref in found.messages:
                    refs[ref.id] = ref
                page = found.next_page_token
                if page is None or handle.stop.is_set():
                    break
        added = 0
        for ref in refs.values():
            if handle.stop.is_set():
                raise Stopped
            if self._messages.has_provider(account.id, ref.id):
                continue
            if self._consume(handle, account, spec, token, ref.id):
                added += 1
        if latest != history_id:
            self._store_cursor(handle, account.id, latest)
            self._log.info(
                "gmail.history_sync",
                account=account.id,
                added=added,
                history_id=latest,
            )
            self._queue.put(
                WatcherEvent(
                    "gmail.history_sync",
                    {"account": account.id, "added": added, "history_id": latest},
                )
            )
        return latest

    def _full_sync(
        self,
        handle: WatcherHandle,
        account: Account,
        spec: ProviderSpec,
        token: str,
        *,
        switch: bool = False,
    ) -> str:
        profile = gmail_api.profile(
            spec,
            token,
            timeout_s=self._api_timeout_s,
            project_id=project_id(self._clients, account),
        )
        baseline = profile.history_id
        if baseline is None:
            raise WatchFailure("gmail_history_unavailable")
        refs = backfill_refs(
            spec,
            token,
            days=self._settings.sweep_initial_days,
            limit=self._settings.sweep_limit,
            timeout_s=self._api_timeout_s,
            project_id=project_id(self._clients, account),
            stop=handle.stop,
        )
        count = 0
        for ref in refs:
            if handle.stop.is_set():
                raise Stopped
            if self._consume(handle, account, spec, token, ref.id):
                count += 1
        self._store_cursor(handle, account.id, baseline)
        if switch:
            self._queue.put(
                WatcherEvent(
                    "inbound.source_switch",
                    {
                        "account": account.id,
                        "from": account.cursor_source or "none",
                        "to": "gmail_api",
                        "backfilled": count,
                    },
                )
            )
        self._log.info(
            "gmail.backfill",
            account=account.id,
            count=count,
            history_id=baseline,
        )
        return baseline

    def _consume(
        self,
        handle: WatcherHandle,
        account: Account,
        spec: ProviderSpec,
        token: str,
        provider_id: str,
    ) -> bool:
        if self._messages.has_provider(account.id, provider_id):
            return False
        incoming = fetch_incoming(
            spec,
            token,
            provider_id,
            api_timeout_s=self._api_timeout_s,
            project_id=project_id(self._clients, account),
            body_max_bytes=self._settings.body_max_bytes,
        )
        if incoming is None:
            return False
        return enqueue_ingest(
            self._queue,
            account.id,
            incoming,
            handle.stop,
            self._settings.ingest_timeout_s,
        )

    def _store_cursor(
        self,
        handle: WatcherHandle,
        account_id: str,
        history_id: str,
    ) -> None:
        job = HistoryJob(
            account_id=account_id,
            history_id=history_id,
            synced_at=utc_now(),
        )
        self._queue.put(job)
        if not wait_done(job.done, handle.stop, self._settings.ingest_timeout_s):
            raise Stopped
        if job.error is not None:
            raise WatchFailure("cursor_failed")

    def _sleep(self, handle: WatcherHandle) -> bool:
        delay = self._settings.api_poll_s * random.uniform(0.8, 1.2)
        deadline = time.monotonic() + delay
        while not handle.stop.is_set():
            if handle.refresh.is_set():
                handle.refresh.clear()
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            handle.stop.wait(timeout=min(1.0, remaining))
        return False

    def _state_ok(self, handle: WatcherHandle, account: Account) -> None:
        with self._guard:
            handle.failures = 0
            handle.next_start = 0.0
            handle.blocked = None
            handle.mode = "api_poll"
        self._queue.put(
            WatcherState(
                account_id=account.id,
                ok=True,
                host=account.address,
                source="gmail_api",
                mode="api_poll",
            )
        )

    def _notify_sync(
        self,
        handle: WatcherHandle,
        *,
        ok: bool,
        reason: str = "",
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
            backoff = self._settings.backoff_s
            index = min(max(handle.failures - 1, 0), len(backoff) - 1)
            retry = backoff[index]
            handle.next_start = time.monotonic() + retry
        return retry

    def _api_failure(self, error: gmail_api.GmailApiFailure) -> WatchFailure:
        if error.auth:
            return WatchFailure("gmail_api_unauthorized", needs_reauth=True)
        if error.code == "gmail_api_disabled":
            return WatchFailure(
                "gmail_api_disabled",
                fatal=True,
                project_id=error.project_id,
            )
        return WatchFailure(error.code)

from __future__ import annotations

import queue
import random
import threading
from datetime import UTC, datetime, timedelta

from downcroc.core.inbound.gmail_ingest import enqueue_ingest, fetch_incoming
from downcroc.core.inbound.gmail_target import project_id
from downcroc.core.inbound.signals import WatcherEvent, WatchFailure
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import (
    AccountNotFound,
    OAuthNotConfigured,
    VaultSecretMissing,
)
from downcroc.domain.messages import normalize_message_id
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.gmail.read import GmailMessageRef, get_message, list_messages
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.config.schema import InboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.messages import MessageRepo


class SweepScheduler:
    """Fleet-level Gmail API completeness sweep, one account per slot."""

    def __init__(
        self,
        queue_: queue.Queue[object],
        tokens: TokenManager,
        clients: OAuthClientService,
        accounts: AccountRepo,
        messages: MessageRepo,
        log: EventLogger,
        settings: InboundSettings,
        api_timeout_s: float,
        initialized_at: str,
    ) -> None:
        self._queue = queue_
        self._tokens = tokens
        self._clients = clients
        self._accounts = accounts
        self._messages = messages
        self._log = log
        self._settings = settings
        self._api_timeout_s = api_timeout_s
        self._initialized_at = initialized_at
        self._stop = threading.Event()

    def start(self) -> threading.Thread:
        thread = threading.Thread(
            target=self._run,
            name="downcroc-gmail-sweep",
            daemon=True,
        )
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            delay = self._settings.sweep_tick_s * (
                1.0 + random.uniform(0.0, self._settings.sweep_slot_jitter)
            )
            if self._stop.wait(timeout=delay):
                return
            try:
                self._slot()
            except Exception as error:  # noqa: BLE001 - the sweep must survive
                self._log.error(
                    "gmail.sweep_failed",
                    error=type(error).__name__,
                )

    def _slot(self) -> None:
        eligible = self._eligible()
        chosen = eligible[: self._settings.sweep_accounts_per_tick]
        for account, spec in chosen:
            if self._stop.is_set():
                return
            self._sweep(account, spec)

    def _eligible(self) -> list[tuple[Account, ProviderSpec]]:
        found: list[tuple[Account, ProviderSpec]] = []
        now = parse_utc(utc_now())
        for account in self._accounts.list():
            if (
                account.status is not AccountStatus.CONNECTED
                or not account.watcher_enabled
            ):
                continue
            spec = self._clients.spec_for_account(account)
            if spec.auth_kind is not AuthKind.OAUTH2 or not spec.api_configured:
                continue
            if self._backing_off(account, now):
                continue
            found.append((account, spec))
        found.sort(key=lambda item: _order(item[0]))
        return found

    def _backing_off(self, account: Account, now: datetime) -> bool:
        if account.consecutive_failures <= 0 or account.last_sweep_at is None:
            return False
        try:
            last = parse_utc(account.last_sweep_at)
        except ValueError:
            return False
        backoff = self._settings.backoff_s
        index = min(account.consecutive_failures - 1, len(backoff) - 1)
        return (now - last).total_seconds() < backoff[index]

    def _sweep(self, account: Account, spec: ProviderSpec) -> None:
        try:
            token = self._tokens.access_token(account, spec=spec)
            refs = self._candidates(account, spec, token)
            found = len(refs)
            ingested = 0
            skipped = 0
            for ref in refs:
                if self._stop.is_set():
                    return
                outcome = self._consume(account, spec, token, ref.id)
                if outcome:
                    ingested += 1
                else:
                    skipped += 1
            self._accounts.sweep_succeeded(account.id, utc_now())
            self._log.info(
                "gmail.sweep",
                account=account.id,
                found=found,
                ingested=ingested,
                skipped=skipped,
                skip_reasons={"not_ingested": skipped} if skipped else {},
            )
            self._queue.put(
                WatcherEvent(
                    "gmail.sweep",
                    {
                        "account": account.id,
                        "found": found,
                        "ingested": ingested,
                        "skipped": skipped,
                        "skip_reasons": ({"not_ingested": skipped} if skipped else {}),
                    },
                )
            )
        except NeedsReauth:
            self._fail(account, "gmail_api_unauthorized")
        except VaultSecretMissing:
            self._fail(account, "credential_missing")
        except OAuthNotConfigured, TokenRefreshFailed, TokenRefreshUnavailable:
            self._fail(account, "oauth_unavailable")
        except WatchFailure as error:
            self._fail(account, error.reason)
        except gmail_api.GmailApiFailure as error:
            self._fail(account, error.code)
            if error.code == "gmail_api_disabled":
                self._queue.put(
                    WatcherEvent(
                        "gmail.api_disabled",
                        {
                            "account": account.id,
                            "project_id": error.project_id,
                        },
                    )
                )
        except Exception as error:  # noqa: BLE001
            self._fail(account, "sweep_failed")
            self._log.error(
                "gmail.sweep_failed",
                account=account.id,
                error=type(error).__name__,
            )

    def _candidates(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
    ) -> list[GmailMessageRef]:
        cutoff = _cutoff(
            account,
            self._settings.sweep_initial_days,
            self._initialized_at if self._settings.ingest_since_init else None,
        )
        query = f"in:inbox after:{cutoff} -in:spam -in:trash"
        refs: dict[str, GmailMessageRef] = {}
        page: str | None = None
        while len(refs) < self._settings.sweep_limit and not self._stop.is_set():
            remaining = self._settings.sweep_limit - len(refs)
            found = list_messages(
                spec,
                token,
                query,
                timeout_s=self._api_timeout_s,
                page_token=page,
                max_results=min(100, remaining),
                project_id=project_id(self._clients, account),
            )
            for ref in found.messages:
                refs.setdefault(ref.id, ref)
            page = found.next_page_token
            if page is None:
                break
        return list(refs.values())

    def _consume(
        self,
        account: Account,
        spec: ProviderSpec,
        token: str,
        provider_id: str,
    ) -> bool:
        if self._messages.has_provider(account.id, provider_id):
            return False
        metadata = get_message(
            spec,
            token,
            provider_id,
            timeout_s=self._api_timeout_s,
            fmt="metadata",
            metadata_headers=("Message-ID",),
            project_id=project_id(self._clients, account),
        )
        header = normalize_message_id(metadata.message_id_header)
        if header is not None:
            existing = self._messages.find_by_message_id(account.id, header)
            if existing is not None:
                self._messages.mark_provider(account.id, header, provider_id)
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
            self._stop,
            self._settings.ingest_timeout_s,
        )

    def _fail(self, account: Account, reason: str) -> None:
        self._accounts.sweep_failed(account.id, reason, utc_now())
        if reason == "gmail_api_unauthorized":
            try:
                self._accounts.mark_needs_reauth(account.id, reason)
            except AccountNotFound:
                return
            self._queue.put(
                WatcherEvent(
                    "account.needs_reauth",
                    {"id": account.id, "reason": reason},
                )
            )
        self._log.warning(
            "gmail.sweep_failed",
            account=account.id,
            reason=reason,
        )


def _order(account: Account) -> tuple[bool, str, str]:
    return (account.last_sweep_at is not None, account.last_sweep_at or "", account.id)


def _cutoff(account: Account, days: int, initialized_at: str | None) -> str:
    moment = datetime.now(UTC) - timedelta(days=days)
    if initialized_at is not None:
        try:
            moment = max(moment, parse_utc(initialized_at))
        except ValueError:
            pass
    if account.last_sweep_at is not None:
        try:
            moment = max(moment, parse_utc(account.last_sweep_at))
        except ValueError:
            pass
    return moment.strftime("%Y/%m/%d")

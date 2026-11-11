from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass

from downcroc.core.accounts.service import AccountsService
from downcroc.core.credentials import CredentialResolver
from downcroc.core.transports import TransportService
from downcroc.core.vault.credentials import CredentialPresence
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    OAuthFailed,
    OAuthUnavailable,
    VaultLocked,
)
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.imap import connection as imap
from downcroc.mail.smtp import sender
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenRefreshFailed, TokenRefreshUnavailable
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger

OK = "ok"
NEEDS_REAUTH = "needs_reauth"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AuthOutcome:
    status: str
    error: str | None = None
    action: str | None = None
    kind: str = "none"
    hint: str | None = None


class AuthPreflight:
    """A bounded, background credential check that never blocks unlock."""

    def __init__(
        self,
        accounts: AccountsService,
        transports: TransportService,
        credentials: CredentialResolver,
        presence: CredentialPresence,
        registry: ProviderRegistry,
        settings: Settings,
        log: EventLogger,
    ) -> None:
        self._accounts = accounts
        self._transports = transports
        self._credentials = credentials
        self._presence = presence
        self._registry = registry
        self._settings = settings
        self._log = log
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    def cancel(self, reason: str) -> None:
        task = self._task
        self._task = None
        if task is None or task.done():
            return
        task.cancel()
        self._log.info("account.auth_check_cancelled", reason=reason)

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        try:
            accounts = self._accounts.auth_candidates()
            semaphore = asyncio.Semaphore(self._settings.connect.auth_check_concurrency)
            outcomes = await asyncio.gather(
                *(self._check(account, semaphore) for account in accounts)
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - the preflight must not crash the daemon
            self._log.error(
                "account.auth_check_error",
                error=error.__class__.__name__,
                detail=str(error)[:500],
            )
            return
        finally:
            self._task = None
        counts = {OK: 0, NEEDS_REAUTH: 0, UNAVAILABLE: 0}
        for outcome in outcomes:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
        self._log.info(
            "account.auth_check_summary",
            checked=len(outcomes),
            ok=counts[OK],
            needs_reauth=counts[NEEDS_REAUTH],
            unavailable=counts[UNAVAILABLE],
        )

    async def _check(
        self, account: Account, semaphore: asyncio.Semaphore
    ) -> AuthOutcome:
        async with semaphore:
            kind = self._auth_kind(account)
            started = time.monotonic()
            self._log.info(
                "account.auth_check_start",
                account=account.id,
                provider=account.provider,
                kind=kind,
            )
            outcome = await self._inspect(account, kind)
            self._accounts.record_auth_check(
                account.id,
                checked_at=utc_now(),
                status=outcome.status,
                error=outcome.error,
                action=outcome.action,
            )
            duration = round((time.monotonic() - started) * 1000)
            if outcome.status == OK:
                self._log.info(
                    "account.auth_check_ok",
                    account=account.id,
                    provider=account.provider,
                    kind=outcome.kind,
                    duration_ms=duration,
                )
            else:
                self._log.warning(
                    "account.auth_check_failed",
                    account=account.id,
                    provider=account.provider,
                    kind=outcome.kind,
                    code=outcome.error,
                    hint=outcome.hint,
                    duration_ms=duration,
                )
            return outcome

    async def _inspect(self, account: Account, kind: str) -> AuthOutcome:
        if account.credential_key is None or not self._presence.present(account):
            return AuthOutcome(
                NEEDS_REAUTH,
                "credential_missing",
                "reconnect",
                "vault",
                "connect the account again",
            )
        enabled = [
            binding for binding in self._transports.list(account.id) if binding.enabled
        ]
        if not enabled:
            return AuthOutcome(
                UNAVAILABLE,
                "transport_disabled",
                "wait",
                "transport",
                "enable a send transport",
            )
        if not self._transports.usable(account):
            return AuthOutcome(
                UNAVAILABLE,
                "transport_unavailable",
                "wait",
                "transport",
                "check the transport health",
            )
        spec = self._registry.get(account.provider)
        try:
            if kind == TransportKind.GMAIL_API.value:
                return await self._check_api(account, spec, enabled)
            if spec.imap_configured:
                return await self._check_imap(account, spec)
            return await self._check_smtp(account, spec)
        except VaultLocked:
            return AuthOutcome(UNAVAILABLE, "vault_locked", "unlock", kind)
        except AccountNeedsReauth:
            return AuthOutcome(
                NEEDS_REAUTH,
                "account_needs_reauth",
                "reconnect",
                kind,
                "connect the account again",
            )
        except CredentialMissing:
            return AuthOutcome(
                NEEDS_REAUTH,
                "credential_missing",
                "reconnect",
                kind,
                "connect the account again",
            )
        except OAuthUnavailable, TokenRefreshUnavailable:
            return AuthOutcome(
                UNAVAILABLE,
                "provider_unavailable",
                "retry",
                kind,
                "try again later",
            )
        except OAuthFailed, TokenRefreshFailed:
            return AuthOutcome(UNAVAILABLE, "oauth_failed", "retry", kind)
        except Exception as error:  # noqa: BLE001 - one account must not stop the check
            return AuthOutcome(
                UNAVAILABLE,
                "auth_check_error",
                "retry",
                kind,
                error.__class__.__name__,
            )

    async def _check_api(
        self,
        account: Account,
        spec: ProviderSpec,
        bindings: list[AccountTransport],
    ) -> AuthOutcome:
        binding = next(
            item for item in bindings if item.kind is TransportKind.GMAIL_API
        )
        token = self._credentials.access_token(
            account,
            spec,
            client_id=binding.oauth_client_id,
        )
        try:
            await asyncio.to_thread(
                gmail_api.profile,
                spec,
                token,
                timeout_s=self._settings.connect.oauth_timeout_s,
            )
        except gmail_api.GmailApiFailure as error:
            status = NEEDS_REAUTH if error.auth else UNAVAILABLE
            action = "reconnect" if error.auth else "retry"
            return AuthOutcome(status, error.code, action, "gmail_api")
        return AuthOutcome(OK, None, None, "gmail_api")

    async def _check_imap(self, account: Account, spec: ProviderSpec) -> AuthOutcome:
        credentials = self._credentials.resolve(account, spec)
        try:
            await asyncio.to_thread(
                imap.login,
                spec,
                account.address,
                password=credentials.password,
                access_token=credentials.access_token,
                timeout_s=self._settings.connect.imap_timeout_s,
            )
        except imap.ImapAuthError:
            return AuthOutcome(
                NEEDS_REAUTH,
                "imap_auth_failed",
                "reconnect",
                "imap",
                "connect the account again",
            )
        except imap.ImapTlsError:
            return AuthOutcome(
                UNAVAILABLE,
                "imap_tls_failed",
                "retry",
                "imap",
                "check the server certificate",
            )
        except imap.ImapNetworkError, imap.ImapProtocolError:
            return AuthOutcome(
                UNAVAILABLE,
                "imap_unreachable",
                "retry",
                "imap",
                "try again later",
            )
        return AuthOutcome(OK, None, None, "imap")

    async def _check_smtp(self, account: Account, spec: ProviderSpec) -> AuthOutcome:
        credentials = self._credentials.resolve(account, spec)
        try:
            await sender.test(
                spec,
                account,
                credentials,
                timeout_s=min(self._settings.outbound.smtp_timeout_s, 10.0),
            )
        except sender.SmtpAuthFailure:
            return AuthOutcome(
                NEEDS_REAUTH,
                "smtp_auth_failed",
                "reconnect",
                "smtp",
                "connect the account again",
            )
        except sender.SmtpFailure as error:
            return AuthOutcome(UNAVAILABLE, error.code, "retry", "smtp")
        return AuthOutcome(OK, None, None, "smtp")

    def _auth_kind(self, account: Account) -> str:
        try:
            spec = self._registry.get(account.provider)
        except Exception:  # noqa: BLE001 - a missing provider is reported by the check
            return "none"
        bindings = [
            binding for binding in self._transports.list(account.id) if binding.enabled
        ]
        if spec.api_configured and any(
            binding.kind is TransportKind.GMAIL_API for binding in bindings
        ):
            return TransportKind.GMAIL_API.value
        if spec.imap_configured:
            return "imap"
        if any(binding.kind is TransportKind.SMTP for binding in bindings):
            return TransportKind.SMTP.value
        return "none"

from __future__ import annotations

import asyncio

from downcroc.core.events import EventBus
from downcroc.core.outbound.credentials import CredentialResolver
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    OAuthFailed,
    OAuthUnavailable,
    SmtpUnavailable,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.jobs import Job
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.imap import connection as imap
from downcroc.mail.imap.folders import find_sent
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import (
    NeedsReauth,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import ConnectSettings, OutboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo


class SentReconciler:
    def __init__(
        self,
        jobs: JobRepo,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        credentials: CredentialResolver,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
        connect: ConnectSettings,
    ) -> None:
        self._jobs = jobs
        self._accounts = accounts
        self._providers = providers
        self._credentials = credentials
        self._bus = bus
        self._log = log
        self._settings = settings
        self._connect = connect

    async def run(self) -> None:
        try:
            self._credentials.ensure_unlocked()
        except VaultLocked:
            return
        for job in self._jobs.list_sending():
            account = self._accounts.get(job.account_id)
            spec = self._providers.get(account.provider)
            found, failure = await self._look_for_sent(job, account, spec)
            if failure is not None:
                self._log.warning(
                    "outbound.reconcile_failed",
                    job=job.id,
                    reason=failure.__class__.__name__,
                )
                continue
            if found:
                self._mark_found(job)
                continue
            await self._recover(job)

    async def _look_for_sent(
        self, job: Job, account: Account, spec: ProviderSpec
    ) -> tuple[bool, Exception | None]:
        found = False
        try:
            credentials = self._credentials.resolve(account, spec)
            for attempt in range(self._settings.reconcile_attempts):
                found = find_sent(
                    spec,
                    account.address,
                    job.message_id,
                    password=credentials.password,
                    access_token=credentials.access_token,
                    timeout_s=self._connect.imap_timeout_s,
                )
                if found:
                    break
                if attempt + 1 < self._settings.reconcile_attempts:
                    await asyncio.sleep(self._settings.reconcile_delay_s)
        except (
            imap.ImapAuthError,
            imap.ImapNetworkError,
            imap.ImapTlsError,
            imap.ImapProtocolError,
            VaultSecretMissing,
            NeedsReauth,
            TokenRefreshUnavailable,
            TokenRefreshFailed,
            CredentialMissing,
            AccountNeedsReauth,
            SmtpUnavailable,
            OAuthFailed,
            OAuthUnavailable,
            VaultLocked,
        ) as error:
            if isinstance(
                error,
                (
                    imap.ImapAuthError,
                    VaultSecretMissing,
                    NeedsReauth,
                ),
            ):
                self._accounts.mark_needs_reauth(account.id, "reconcile_auth_failed")
            return found, error
        return found, None

    def _mark_found(self, job: Job) -> None:
        sent = self._jobs.mark_reconciled(job.id, utc_now())
        self._bus.publish(
            "job.sent",
            {
                "id": sent.id,
                "batch": sent.batch_id,
                "message_id": sent.message_id,
            },
        )
        self._log.info(
            "job.reconciled",
            job=job.id,
            message_id=job.message_id,
            found=True,
        )

    async def _recover(self, job: Job) -> None:
        self._jobs.mark_queued(
            job.id,
            code="not_accepted",
            message="the message was not found in the sent folder",
            retryable=True,
        )
        self._log.info(
            "job.reconciled",
            job=job.id,
            message_id=job.message_id,
            found=False,
        )

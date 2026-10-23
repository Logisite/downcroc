from __future__ import annotations

import asyncio
import time
import uuid

from downcroc.core.events import EventBus
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import (
    AccountNeedsReauth,
    ContentCorrupt,
    ContentMissing,
    CredentialMissing,
    DomainError,
    InvalidJob,
    JobNotSendable,
    OAuthFailed,
    OAuthUnavailable,
    SmtpUnavailable,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.jobs import Job, NewJob
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.secrets import secret_key
from downcroc.domain.validators import ADDRESS
from downcroc.mail.imap import connection as imap
from downcroc.mail.imap.folders import find_sent
from downcroc.mail.mime.builder import build_message, mint_message_id, prepare_for_send
from downcroc.mail.smtp import sender
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings, OutboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo


class OutboundService:
    def __init__(
        self,
        jobs: JobRepo,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        content: ContentStore,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
        connect: ConnectSettings,
    ) -> None:
        self._jobs = jobs
        self._accounts = accounts
        self._providers = providers
        self._vault = vault
        self._tokens = tokens
        self._content = content
        self._bus = bus
        self._log = log
        self._settings = settings
        self._connect = connect
        self._owner = f"outbound-{uuid.uuid4().hex[:12]}"

    def create(
        self,
        *,
        account_id: str,
        recipient: str,
        recipient_name: str | None,
        subject: str,
        text: str,
        html: str | None,
        batch_id: str = "manual",
    ) -> Job:
        account = self._accounts.get(account_id)
        recipient = recipient.strip().lower()
        subject = subject.strip()
        fields: dict[str, str] = {}
        if not ADDRESS.fullmatch(recipient):
            fields["recipient"] = "must be an email address"
        if not subject:
            fields["subject"] = "must not be empty"
        if not text.strip() and not (html or "").strip():
            fields["text"] = "a text or html body is required"
        if not batch_id.strip():
            fields["batch_id"] = "must not be empty"
        if fields:
            raise InvalidJob("the job fields are not valid", fields=fields)
        job_id = new_id("job")
        message_id = mint_message_id(account.address, self._jobs.message_id_exists)
        now = utc_now()
        payload = build_message(
            from_address=account.address,
            from_name=account.label,
            to_address=recipient,
            to_name=recipient_name,
            subject=subject,
            text=text,
            html=html,
            message_id=message_id,
        )
        stored = self._content.put_job_message(job_id, payload)
        return self._jobs.create(
            NewJob(
                id=job_id,
                batch_id=batch_id,
                account_id=account.id,
                recipient=recipient,
                recipient_name=recipient_name,
                vars_json="{}",
                subject=subject,
                body_ref=stored.path,
                message_id=message_id,
                created_at=now,
            )
        )

    def list(
        self,
        *,
        batch_id: str | None = None,
        account_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ) -> list[Job]:
        return self._jobs.list(
            batch_id=batch_id,
            account_id=account_id,
            state=state,
            limit=limit,
        )

    def get(self, job_id: str) -> Job:
        return self._jobs.get(job_id)

    async def send(self, job_id: str) -> Job:
        self._vault.ensure_unlocked()
        job = self._jobs.get(job_id)
        account = self._accounts.get(job.account_id)
        self._require_connected(account)
        spec = self._providers.get(account.provider)
        claimed = self._jobs.claim(
            job_id,
            self._owner,
            utc_now(),
            utc_after(self._settings.lease_seconds),
        )
        if claimed is None:
            raise JobNotSendable(
                "the job is not ready to send",
                hint="only queued or retry_wait jobs can be sent",
            )
        started = time.monotonic()
        self._log.info(
            "job.send_start",
            job=claimed.id,
            account=claimed.account_id,
            attempt=claimed.attempts,
        )
        try:
            credentials = self._credentials(account, spec)
            payload = self._content.read_bytes(claimed.body_ref)
            wire = prepare_for_send(
                payload,
                from_address=account.address,
                from_name=account.label,
                to_address=claimed.recipient,
                to_name=claimed.recipient_name,
                subject=claimed.subject,
                message_id=claimed.message_id,
            )
            result = await sender.send(
                spec,
                account,
                credentials,
                claimed.recipient,
                wire,
                timeout_s=self._settings.smtp_timeout_s,
            )
        except sender.SmtpAuthFailure as error:
            self._accounts.mark_needs_reauth(account.id, error.code)
            self._jobs.mark_queued(
                claimed.id,
                code=error.code,
                message=error.message,
                retryable=False,
            )
            self._log.warning(
                "smtp.rejected",
                code=error.code,
                transient=False,
                job=claimed.id,
            )
            raise AccountNeedsReauth(
                "the mailbox rejected the send credential",
                hint="connect the account again",
            ) from error
        except sender.SmtpFailure as error:
            if error.transient:
                self._jobs.mark_retry(
                    claimed.id,
                    code=error.code,
                    message=error.message,
                    next_attempt_at=utc_now(),
                    retryable=True,
                )
            else:
                self._jobs.mark_failed(
                    claimed.id,
                    code=error.code,
                    message=error.message,
                    retryable=False,
                )
            self._log.warning(
                "smtp.rejected",
                code=error.code,
                transient=error.transient,
                job=claimed.id,
            )
            return self._jobs.get(claimed.id)
        except AccountNeedsReauth:
            self._jobs.mark_queued(
                claimed.id,
                code="account_needs_reauth",
                message="the account must be reconnected",
                retryable=False,
            )
            raise
        except CredentialMissing, OAuthFailed, OAuthUnavailable, VaultLocked:
            self._jobs.mark_queued(
                claimed.id,
                code="send_unavailable",
                message="the send credential is not available",
                retryable=True,
            )
            raise
        except SmtpUnavailable:
            self._jobs.mark_retry(
                claimed.id,
                code="smtp_unavailable",
                message="the send credential could not be refreshed",
                next_attempt_at=utc_now(),
                retryable=True,
            )
            raise
        except (ContentCorrupt, ContentMissing, ValueError) as error:
            self._jobs.mark_failed(
                claimed.id,
                code="send_preparation_failed",
                message=error.__class__.__name__,
                retryable=False,
            )
            self._log.warning(
                "smtp.rejected",
                code="send_preparation_failed",
                transient=False,
                job=claimed.id,
            )
            raise
        self._log.info(
            "smtp.connected",
            host=spec.smtp_host,
            duration_ms=result.connect_ms,
            job=claimed.id,
        )
        self._log.info(
            "smtp.accepted",
            job=claimed.id,
            message_id=claimed.message_id,
            duration_ms=result.accepted_ms,
        )
        sent = self._jobs.mark_sent(claimed.id, utc_now())
        self._bus.publish(
            "job.sent",
            {"id": sent.id, "batch": sent.batch_id, "message_id": sent.message_id},
        )
        self._log.info(
            "job.sent",
            job=sent.id,
            message_id=sent.message_id,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return sent

    async def reconcile(self) -> None:
        try:
            self._vault.ensure_unlocked()
        except VaultLocked:
            return
        for job in self._jobs.list_sending():
            account = self._accounts.get(job.account_id)
            spec = self._providers.get(account.provider)
            found = False
            failure: Exception | None = None
            try:
                credentials = self._credentials(account, spec)
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
                    self._accounts.mark_needs_reauth(
                        account.id, "reconcile_auth_failed"
                    )
                failure = error
            if failure is not None:
                self._log.warning(
                    "outbound.reconcile_failed",
                    job=job.id,
                    reason=failure.__class__.__name__,
                )
                continue
            if found:
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
            else:
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
                try:
                    await self.send(job.id)
                except DomainError as error:
                    self._log.warning(
                        "outbound.recover_failed",
                        job=job.id,
                        reason=error.code,
                    )

    def _credentials(
        self, account: Account, spec: ProviderSpec
    ) -> sender.SmtpCredentials:
        if spec.auth_kind is AuthKind.OAUTH2:
            try:
                token = self._tokens.access_token(account)
            except NeedsReauth as error:
                self._accounts.mark_needs_reauth(account.id, error.reason)
                raise AccountNeedsReauth(
                    "the mailbox needs to be reconnected",
                    hint="start a new connect attempt",
                ) from error
            except TokenRefreshUnavailable as error:
                raise SmtpUnavailable(
                    "the token endpoint could not be reached",
                    hint="try again later",
                ) from error
            except TokenRefreshFailed as error:
                raise OAuthFailed(
                    "the access token could not be refreshed",
                    hint="check the provider client configuration",
                ) from error
            except VaultSecretMissing as error:
                self._accounts.mark_needs_reauth(account.id, "missing_refresh_token")
                raise AccountNeedsReauth(
                    "the refresh token is missing from the vault",
                    hint="start a new connect attempt",
                ) from error
            return sender.SmtpCredentials(
                address=account.address,
                auth_kind=AuthKind.OAUTH2,
                access_token=token,
            )
        key = account.credential_key or secret_key(account.id, "app_password")
        try:
            secret = self._vault.get_secret(key)
        except VaultSecretMissing as error:
            self._accounts.mark_needs_reauth(account.id, "credential_missing")
            raise CredentialMissing(
                "the credential is missing from the vault",
                hint="connect the account again",
            ) from error
        return sender.SmtpCredentials(
            address=account.address,
            auth_kind=AuthKind.APP_PASSWORD,
            password=secret.value,
        )

    def _require_connected(self, account: Account) -> None:
        if account.status is AccountStatus.NEEDS_REAUTH:
            raise AccountNeedsReauth(
                "the account needs to be reconnected",
                hint="start a new connect attempt",
            )
        if account.status is not AccountStatus.CONNECTED:
            raise AccountNeedsReauth(
                "the account is not connected",
                hint="connect the account before sending",
            )

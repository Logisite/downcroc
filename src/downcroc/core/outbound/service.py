from __future__ import annotations

import time
import uuid

from downcroc.core.events import EventBus
from downcroc.core.outbound.credentials import CredentialResolver
from downcroc.core.outbound.reconcile import SentReconciler
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import (
    AccountNeedsReauth,
    ContentCorrupt,
    ContentMissing,
    CredentialMissing,
    InvalidJob,
    JobNotSendable,
    OAuthFailed,
    OAuthUnavailable,
    SmtpUnavailable,
    VaultLocked,
)
from downcroc.domain.jobs import Job, JobState, NewJob
from downcroc.domain.validators import ADDRESS
from downcroc.mail.mime.builder import build_message, mint_message_id, prepare_for_send
from downcroc.mail.smtp import sender
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
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
        self._content = content
        self._bus = bus
        self._log = log
        self._settings = settings
        self._credentials = CredentialResolver(accounts, vault, tokens)
        self._reconciler = SentReconciler(
            jobs,
            accounts,
            providers,
            self._credentials,
            bus,
            log,
            settings,
            connect,
        )
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
                created_at=utc_now(),
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
        self._credentials.ensure_unlocked()
        job = self._jobs.get(job_id)
        account = self._accounts.get(job.account_id)
        self._require_connected(account)
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
        return await self.deliver(claimed, account)

    async def deliver(self, job: Job, account: Account | None = None) -> Job:
        self._credentials.ensure_unlocked()
        claimed = job
        if claimed.state is not JobState.SENDING or claimed.lease_owner is None:
            raise JobNotSendable("the job is not leased for sending")
        account = account or self._accounts.get(claimed.account_id)
        self._require_connected(account)
        spec = self._providers.get(account.provider)
        started = time.monotonic()
        self._log.info(
            "job.send_start",
            job=claimed.id,
            account=claimed.account_id,
            attempt=claimed.attempts,
        )
        try:
            credentials = self._credentials.resolve(account, spec)
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
        await self._reconciler.run()

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

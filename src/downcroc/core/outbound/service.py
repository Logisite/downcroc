from __future__ import annotations

import time
import uuid

from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.outbound.attempts import AttemptRecorder
from downcroc.core.outbound.reconcile import SentReconciler
from downcroc.core.outbound.smtp_delivery import SmtpDelivery
from downcroc.core.stats import StatsService
from downcroc.core.transports import TransportService
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
    TransportUnavailable,
    VaultLocked,
)
from downcroc.domain.jobs import Job, JobState, NewJob
from downcroc.domain.transports import TransportKind
from downcroc.domain.validators import ADDRESS
from downcroc.mail.mime.builder import build_message, mint_message_id, prepare_for_send
from downcroc.mail.smtp import sender
from downcroc.mail.smtp.session import SmtpSessionPool
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings, OutboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class OutboundService:
    def __init__(
        self,
        jobs: JobRepo,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        content: ContentStore,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
        connect: ConnectSettings,
        send_attempts: SendAttemptRepo,
        transports: TransportService,
    ) -> None:
        self._jobs = jobs
        self._accounts = accounts
        self._providers = providers
        self._content = content
        self._stats = stats
        self._bus = bus
        self._log = log
        self._settings = settings
        self._transports = transports
        self._credentials = CredentialResolver(accounts, vault, tokens)
        self._pool = SmtpSessionPool(settings, log)
        self._recorder = AttemptRecorder(send_attempts)
        self._smtp = SmtpDelivery(
            jobs, transports, self._pool, self._recorder, bus, log, settings
        )
        self._reconciler = SentReconciler(
            jobs,
            accounts,
            providers,
            self._credentials,
            stats,
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
        offset: int = 0,
    ) -> list[Job]:
        return self._jobs.list(
            batch_id=batch_id,
            account_id=account_id,
            state=state,
            limit=limit,
            offset=offset,
        )

    def count(
        self,
        *,
        batch_id: str | None = None,
        account_id: str | None = None,
        state: str | None = None,
    ) -> int:
        return self._jobs.count(
            batch_id=batch_id,
            account_id=account_id,
            state=state,
        )

    def get(self, job_id: str) -> Job:
        return self._jobs.get(job_id)

    async def send(self, job_id: str) -> Job:
        self._credentials.ensure_unlocked()
        job = self._jobs.get(job_id)
        account = self._sender_for(job)
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

    def _sender_for(self, job: Job) -> Account:
        if job.account_id is not None:
            return self._accounts.get(job.account_id)
        for account in self._accounts.list():
            if (
                account.status is AccountStatus.CONNECTED
                and account.policy.enabled
                and self._transports.lanes(account) > 0
            ):
                return account
        raise AccountNeedsReauth(
            "no mailbox can carry this job",
            hint="connect an account before sending",
        )

    async def deliver(self, job: Job, account: Account | None = None) -> Job:
        self._credentials.ensure_unlocked()
        claimed = job
        if claimed.state is not JobState.SENDING or claimed.lease_owner is None:
            raise JobNotSendable("the job is not leased for sending")
        account = account or self._accounts.get(claimed.account_id)
        self._require_connected(account)
        spec = self._providers.get(account.provider)
        bindings = [
            binding
            for binding in self._transports.usable(account)
            if binding.kind is TransportKind.SMTP
        ]
        if not bindings:
            raise TransportUnavailable(
                "the mailbox has no healthy send transport",
                hint="add or test a transport binding for the account",
            )
        started = time.monotonic()
        started_at = utc_now()
        self._log.info(
            "job.send_start",
            job=claimed.id,
            account=account.id,
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
        except sender.SmtpAuthFailure as error:
            self._prepare_failed(
                claimed,
                account,
                started_at,
                outcome="failed",
                code=error.code,
                message=error.message,
                accepted=False,
            )
            self._accounts.mark_needs_reauth(account.id, error.code)
            self._jobs.mark_queued(
                claimed.id,
                code=error.code,
                message=error.message,
                retryable=False,
            )
            raise AccountNeedsReauth(
                "the mailbox rejected the send credential",
                hint="connect the account again",
            ) from error
        except AccountNeedsReauth:
            self._prepare_failed(
                claimed,
                account,
                started_at,
                outcome="deferred",
                code="account_needs_reauth",
                message="the account must be reconnected",
            )
            self._jobs.mark_queued(
                claimed.id,
                code="account_needs_reauth",
                message="the account must be reconnected",
                retryable=False,
            )
            raise
        except CredentialMissing, OAuthFailed, OAuthUnavailable, VaultLocked:
            self._prepare_failed(
                claimed,
                account,
                started_at,
                outcome="deferred",
                code="send_unavailable",
                message="the send credential is not available",
            )
            self._jobs.mark_queued(
                claimed.id,
                code="send_unavailable",
                message="the send credential is not available",
                retryable=True,
            )
            raise
        except SmtpUnavailable:
            self._prepare_failed(
                claimed,
                account,
                started_at,
                outcome="deferred",
                code="smtp_unavailable",
                message="the send credential could not be refreshed",
            )
            self._jobs.mark_retry(
                claimed.id,
                code="smtp_unavailable",
                message="the send credential could not be refreshed",
                next_attempt_at=utc_now(),
                retryable=True,
            )
            raise
        except (ContentCorrupt, ContentMissing, ValueError) as error:
            self._prepare_failed(
                claimed,
                account,
                started_at,
                outcome="failed",
                code="send_preparation_failed",
                message=error.__class__.__name__,
                accepted=False,
            )
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
        sent = await self._smtp.deliver(
            claimed, account, spec, credentials, wire, started_at
        )
        if sent.state is JobState.SENT and sent.id == claimed.id:
            self._sent(sent, account, started)
        return sent

    def _prepare_failed(
        self,
        job: Job,
        account: Account,
        started_at: str,
        *,
        outcome: str,
        code: str,
        message: str,
        accepted: bool | None = None,
    ) -> None:
        self._recorder.record(
            job,
            account,
            None,
            "smtp",
            started_at,
            outcome=outcome,
            accepted=accepted,
            code=code,
            message=message,
        )

    def _sent(self, job: Job, account: Account, started: float) -> None:
        self._stats.record_sent(job, account.id)
        self._bus.publish(
            "job.sent",
            {"id": job.id, "batch": job.batch_id, "message_id": job.message_id},
        )
        self._log.info(
            "job.sent",
            job=job.id,
            message_id=job.message_id,
            duration_ms=round((time.monotonic() - started) * 1000),
        )

    async def reconcile(self) -> None:
        await self._reconciler.run()

    async def close_sessions(self, reason: str) -> None:
        await self._pool.close_all(reason)

    async def reap_sessions(self) -> None:
        await self._pool.reap()

    async def prune_sessions(self, valid: set[str]) -> None:
        await self._pool.prune(valid)

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

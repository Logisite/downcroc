from __future__ import annotations

import time
import uuid

from downcroc.core.accounts import AccountEligibility
from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.outbound.attempts import AttemptRecorder
from downcroc.core.outbound.attempts.quota import QuotaAccountant
from downcroc.core.outbound.jobs.create import require_usable
from downcroc.core.outbound.jobs.facade import JobFacade
from downcroc.core.outbound.jobs.manual import ManualJobs
from downcroc.core.outbound.reconcile import SentReconciler
from downcroc.core.outbound.transports import (
    DeliveryOutcome,
    GmailDelivery,
    SmtpDelivery,
    TransportDelivery,
)
from downcroc.core.policy import PolicyResolver
from downcroc.core.stats import StatsService
from downcroc.core.transports import TransportService
from downcroc.core.vault import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    ContentCorrupt,
    ContentMissing,
    JobNotFound,
    JobNotSendable,
)
from downcroc.domain.jobs import Job, JobState, SenderPolicy
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.mime.builder import prepare_for_send
from downcroc.mail.smtp.session import SmtpSessionPool
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings, OutboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class OutboundService(JobFacade):
    def __init__(
        self,
        jobs: JobRepo,
        batches: BatchRepo,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        clients: OAuthClientService,
        content: ContentStore,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
        connect: ConnectSettings,
        send_attempts: SendAttemptRepo,
        transports: TransportService,
        policy: PolicyResolver,
        eligibility: AccountEligibility,
        quota: QuotaRepo,
        connectivity: object | None = None,
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
        self._policy = policy
        self._quota = quota
        self._credentials = CredentialResolver(accounts, vault, tokens, clients)
        self._accountant = QuotaAccountant(quota, send_attempts, bus, log)
        self._pool = SmtpSessionPool(settings, log)
        self._connectivity = connectivity
        self._attempts = send_attempts
        self._recorder = AttemptRecorder(send_attempts)
        smtp = SmtpDelivery(transports, self._pool, self._recorder, bus, log, settings)
        gmail = GmailDelivery(transports, self._recorder, clients, bus, log, settings)
        self._delivery = TransportDelivery(
            transports,
            self._credentials,
            smtp,
            gmail,
            transports.limiter,
            self._bus,
            log,
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
        self._manual = ManualJobs(
            accounts,
            jobs,
            content,
            transports,
            policy,
            batches,
            eligibility,
        )

    async def send(self, job_id: str) -> Job:
        self._require_online()
        self._credentials.ensure_unlocked()
        job = self._jobs.get(job_id)
        account = self._manual.sender_for(job)
        require_usable(account)
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
        return await self.deliver(claimed, account, manual=True)

    async def deliver(
        self,
        job: Job,
        account: Account | None = None,
        *,
        manual: bool = False,
        allowed_kinds: frozenset | None = None,
    ) -> Job:
        self._require_online()
        self._log.debug("outbound.unlock", job=job.id)
        self._credentials.ensure_unlocked()
        self._log.debug("outbound.account", job=job.id)
        claimed = job
        if claimed.state is not JobState.SENDING or claimed.lease_owner is None:
            raise JobNotSendable("the job is not leased for sending")
        account = account or self._accounts.get(claimed.account_id)
        require_usable(account)
        self._log.debug(
            "outbound.deliver",
            job=claimed.id,
            account=account.id,
            manual=manual,
        )
        if allowed_kinds is None:
            allowed_kinds = self._transports.allowed_kinds(
                account,
                pinned=claimed.sender_policy is SenderPolicy.PINNED,
            )
        policy = self._policy.effective(account)
        day = self._policy.day()
        attempt_id = new_id("att")
        started_at = utc_now()
        if not self._accountant.reserve(
            account,
            day,
            policy.daily_allowance,
            attempt_id=attempt_id,
            job_id=claimed.id,
            started_at=started_at,
            manual=manual,
        ):
            return self._jobs.mark_queued(claimed.id, code="allowance_spent")
        self._log.debug(
            "outbound.reserved",
            job=claimed.id,
            account=account.id,
            attempt=attempt_id,
        )
        spec = self._providers.get(account.provider)
        started = time.monotonic()
        self._log.info(
            "job.send_start",
            job=claimed.id,
            account=account.id,
            attempt=claimed.attempts,
        )
        try:
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
        except (ContentCorrupt, ContentMissing, ValueError) as error:
            self._prepare_failed(claimed, account, started_at, attempt_id, error)
            self._jobs.mark_failed(
                claimed.id,
                code="send_preparation_failed",
                message=error.__class__.__name__,
                retryable=False,
            )
            self._accountant.release(
                account.id,
                day,
                "send_preparation_failed",
                attempt_id,
                job_id=claimed.id,
            )
            raise
        try:
            outcome = await self._delivery.deliver(
                claimed,
                account,
                spec,
                wire,
                started_at,
                attempt_id,
                allowed_kinds,
            )
        except BaseException as error:
            self._finish_attempt(
                claimed,
                account,
                None,
                "pending",
                attempt_id,
                outcome="failed",
                code=error.__class__.__name__,
                message=str(error)[:500],
            )
            self._accountant.release(
                account.id,
                day,
                "send_exception",
                attempt_id,
                job_id=claimed.id,
            )
            raise
        return self._apply(claimed, account, outcome, started, day, attempt_id)

    def _apply(
        self,
        job: Job,
        account: Account,
        outcome: DeliveryOutcome,
        started: float,
        day: str,
        attempt_id: str,
    ) -> Job:
        limit = self._policy.effective(account).daily_allowance
        if outcome.status in {"deferred", "reauth", "failed"}:
            self._finish_attempt(
                job,
                account,
                outcome.binding,
                outcome.binding.kind.value if outcome.binding else "pending",
                attempt_id,
                outcome="deferred" if outcome.status == "deferred" else "failed",
                code=outcome.code or outcome.status,
                message=outcome.message,
            )
        if outcome.status == "sent":
            sent = self._jobs.mark_sent(job.id, utc_now())
            self._sent(sent, account, started, outcome.binding)
            self._accountant.commit(account.id, day, attempt_id, limit)
            return sent
        if outcome.status == "uncertain":
            result = self._jobs.mark_sent_unconfirmed(
                job.id,
                code=outcome.code or "send_uncertain",
                message=outcome.message or "the send result is unknown",
            )
            self._log.warning(
                "job.sent_unconfirmed",
                job=job.id,
                account=account.id,
                code=outcome.code,
            )
            self._accountant.commit(account.id, day, attempt_id, limit)
            return result
        if outcome.status == "reauth":
            self._accounts.mark_needs_reauth(
                account.id, outcome.code or "account_needs_reauth"
            )
            self._finish_attempt(
                job,
                account,
                outcome.binding,
                outcome.binding.kind.value if outcome.binding else "pending",
                attempt_id,
                outcome="failed",
                code=outcome.code or "account_needs_reauth",
                message=outcome.message or "the mailbox must be reconnected",
            )
            self._jobs.mark_queued(
                job.id,
                code=outcome.code,
                message=outcome.message,
                retryable=False,
            )
            self._log.warning(
                "job.blocked",
                job=job.id,
                account=account.id,
                code=outcome.code or "account_needs_reauth",
                retryable=False,
            )
            self._bus.publish(
                "job.blocked",
                {
                    "job": job.id,
                    "account": account.id,
                    "code": outcome.code or "account_needs_reauth",
                    "retryable": False,
                },
            )
            self._accountant.release(
                account.id,
                day,
                outcome.code or "account_needs_reauth",
                attempt_id,
                job_id=job.id,
            )
            raise AccountNeedsReauth(
                "the mailbox must be reconnected",
                hint="connect the account again",
            )
        if outcome.status == "deferred":
            next_attempt = (
                utc_after(outcome.retry_after_s)
                if outcome.retry_after_s is not None
                else utc_now()
            )
            self._accountant.release(
                account.id,
                day,
                outcome.code or "send_deferred",
                attempt_id,
                job_id=job.id,
            )
            return self._jobs.mark_retry(
                job.id,
                code=outcome.code or "send_deferred",
                message=outcome.message or "",
                next_attempt_at=next_attempt,
                retryable=True,
            )
        self._accountant.release(
            account.id,
            day,
            outcome.code or "send_failed",
            attempt_id,
            job_id=job.id,
        )
        self._log.warning(
            "job.failed",
            job=job.id,
            account=account.id,
            code=outcome.code or "send_failed",
            detail=(outcome.message or "")[:300],
        )
        return self._jobs.mark_failed(
            job.id,
            code=outcome.code or "send_failed",
            message=outcome.message or "",
            retryable=False,
        )

    def _finish_attempt(
        self,
        job: Job,
        account: Account,
        binding,
        transport: str,
        attempt_id: str,
        *,
        outcome: str,
        code: str | None,
        message: str | None,
    ) -> None:
        self._recorder.record(
            job,
            account,
            binding,
            transport,
            utc_now(),
            attempt_id=attempt_id,
            outcome=outcome,
            accepted=False,
            code=code,
            message=message,
        )

    def _prepare_failed(
        self,
        job: Job,
        account: Account,
        started_at: str,
        attempt_id: str,
        error: Exception,
    ) -> None:
        self._recorder.record(
            job,
            account,
            None,
            "pending",
            started_at,
            attempt_id=attempt_id,
            outcome="failed",
            accepted=False,
            code="send_preparation_failed",
            message=error.__class__.__name__,
        )
        self._log.warning(
            "smtp.rejected",
            code="send_preparation_failed",
            transient=False,
            job=job.id,
        )

    def _sent(self, job: Job, account: Account, started: float, binding) -> None:
        self._stats.record_sent(job, account.id)
        transport = binding.kind.value if binding is not None else "pending"
        thread = self._thread_fields(job)
        self._bus.publish(
            "job.sent",
            {
                "id": job.id,
                "batch": job.batch_id,
                "message_id": job.message_id,
                "account": account.id,
                "transport": transport,
                "binding": binding.id if binding is not None else None,
                **thread,
            },
        )
        self._log.info(
            "job.sent",
            job=job.id,
            account=account.id,
            message_id=job.message_id,
            transport=transport,
            binding=binding.id if binding is not None else None,
            duration_ms=round((time.monotonic() - started) * 1000),
            **thread,
        )

    def _thread_fields(self, job: Job) -> dict[str, object]:
        in_reply_to = None
        references = 0
        current = job.parent_job_id
        seen: set[str] = set()
        while current is not None and current not in seen and references < 1000:
            seen.add(current)
            try:
                parent = self._jobs.get(current)
            except JobNotFound:
                break
            if in_reply_to is None:
                in_reply_to = parent.message_id
            references += 1
            current = parent.parent_job_id
        return {
            "thread_root": job.thread_root_job_id,
            "parent_job": job.parent_job_id,
            "in_reply_to": in_reply_to,
            "references_count": references,
        }

    async def reconcile(self) -> None:
        await self._reconciler.run()

    async def close_sessions(self, reason: str) -> None:
        await self._pool.close_all(reason)
        gmail_api.close()

    async def reap_sessions(self) -> None:
        if self._connectivity is not None and not self._connectivity.online:
            return
        await self._pool.reap()

    async def prune_sessions(self, valid: set[str]) -> None:
        await self._pool.prune(valid)

    async def verify_sessions(self) -> None:
        await self._pool.verify_all()

    def _require_online(self) -> None:
        if self._connectivity is not None and not self._connectivity.online:
            raise JobNotSendable(
                "the internet is down",
                hint="sending is paused and resumes when connectivity returns",
            )

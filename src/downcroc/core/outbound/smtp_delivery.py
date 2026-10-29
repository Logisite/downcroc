from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.core.outbound.attempts import AttemptRecorder
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import AccountNeedsReauth, TransportUnavailable
from downcroc.domain.jobs import Job
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.mail.smtp import sender
from downcroc.mail.smtp.session import SmtpSessionPool
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import OutboundSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.jobs import JobRepo


class SmtpDelivery:
    """Delivers a leased job across the mailbox's healthy SMTP bindings."""

    def __init__(
        self,
        jobs: JobRepo,
        transports: TransportService,
        pool: SmtpSessionPool,
        recorder: AttemptRecorder,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
    ) -> None:
        self._jobs = jobs
        self._transports = transports
        self._pool = pool
        self._recorder = recorder
        self._bus = bus
        self._log = log
        self._settings = settings

    async def deliver(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        credentials: sender.SmtpCredentials,
        wire: bytes,
        started_at: str,
    ) -> Job:
        bindings = self._bindings(account)
        if not bindings:
            raise TransportUnavailable(
                "the mailbox has no healthy send transport",
                hint="add or test a transport binding for the account",
            )
        auth_error: sender.SmtpAuthFailure | None = None
        last_error: sender.SmtpFailure | None = None
        for binding in bindings:
            result, error = await self._attempt(
                job, account, spec, binding, credentials, wire, started_at
            )
            if result is not None:
                return self._sent(job, account, result)
            if isinstance(error, sender.SmtpAuthFailure):
                auth_error = error
                continue
            if error is not None and not error.transient:
                return self._jobs.get(job.id)
            last_error = error
        if auth_error is not None:
            return self._auth_failed(job, account, auth_error)
        return self._retry(job, last_error)

    def _bindings(self, account: Account) -> list[AccountTransport]:
        return [
            binding
            for binding in self._transports.usable(account)
            if binding.kind is TransportKind.SMTP
        ]

    async def _attempt(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        binding: AccountTransport,
        credentials: sender.SmtpCredentials,
        wire: bytes,
        started_at: str,
    ) -> tuple[sender.SmtpSendResult | None, sender.SmtpFailure | None]:
        self._bus.publish(
            "transport.selected",
            {
                "job": job.id,
                "account": account.id,
                "binding": binding.id,
                "transport": binding.kind.value,
                "reason": "priority",
            },
        )
        try:
            result = await self._pool.send(
                binding.id,
                spec,
                account,
                credentials,
                job.recipient,
                wire,
                timeout_s=self._settings.smtp_timeout_s,
            )
        except sender.SmtpAuthFailure as error:
            self._failed(job, account, binding, started_at, error, auth=True)
            return None, error
        except sender.SmtpFailure as error:
            self._failed(job, account, binding, started_at, error)
            return None, error
        self._recorder.record(
            job,
            account,
            binding,
            binding.kind.value,
            started_at,
            outcome="sent",
            accepted=True,
        )
        self._transports.mark_success(binding)
        self._bus.publish(
            "transport.sent",
            {
                "job": job.id,
                "account": account.id,
                "binding": binding.id,
                "transport": binding.kind.value,
                "provider_message_id": None,
            },
        )
        return result, None

    def _failed(
        self,
        job: Job,
        account: Account,
        binding: AccountTransport,
        started_at: str,
        error: sender.SmtpFailure,
        *,
        auth: bool = False,
    ) -> None:
        self._recorder.record(
            job,
            account,
            binding,
            binding.kind.value,
            started_at,
            outcome="failed" if auth or not error.transient else "deferred",
            accepted=False,
            code=error.code,
            message=error.message,
        )
        self._transports.mark_failure(
            binding,
            code=error.code,
            message=error.message,
            transient=error.transient,
            auth=auth,
        )
        self._bus.publish(
            "transport.failed",
            {
                "job": job.id,
                "account": account.id,
                "binding": binding.id,
                "transport": binding.kind.value,
                "error_code": error.code,
                "accepted": False,
            },
        )
        self._log.warning(
            "smtp.rejected",
            code=error.code,
            transient=error.transient,
            job=job.id,
        )

    def _sent(
        self,
        job: Job,
        account: Account,
        result: sender.SmtpSendResult,
    ) -> Job:
        self._log.info(
            "smtp.accepted",
            job=job.id,
            message_id=job.message_id,
            duration_ms=result.accepted_ms,
        )
        return self._jobs.mark_sent(job.id, utc_now())

    def _auth_failed(
        self,
        job: Job,
        account: Account,
        error: sender.SmtpAuthFailure,
    ) -> Job:
        self._jobs.mark_queued(
            job.id,
            code=error.code,
            message=error.message,
            retryable=False,
        )
        raise AccountNeedsReauth(
            "the mailbox rejected the send credential",
            hint="connect the account again",
        ) from error

    def _retry(self, job: Job, error: sender.SmtpFailure | None) -> Job:
        code = error.code if error is not None else "transport_unavailable"
        message = error.message if error is not None else ""
        self._jobs.mark_retry(
            job.id,
            code=code,
            message=message,
            next_attempt_at=utc_now(),
            retryable=True,
        )
        return self._jobs.get(job.id)

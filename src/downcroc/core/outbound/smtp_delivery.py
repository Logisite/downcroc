from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.core.outbound.attempts import AttemptRecorder
from downcroc.core.outbound.result import AttemptResult
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account
from downcroc.domain.jobs import Job
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport
from downcroc.mail.smtp import sender
from downcroc.mail.smtp.session import SmtpSessionPool
from downcroc.runtime.config.schema import OutboundSettings
from downcroc.runtime.logging.setup import EventLogger


class SmtpDelivery:
    """Runs one SMTP attempt through one binding."""

    def __init__(
        self,
        transports: TransportService,
        pool: SmtpSessionPool,
        recorder: AttemptRecorder,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
    ) -> None:
        self._transports = transports
        self._pool = pool
        self._recorder = recorder
        self._bus = bus
        self._log = log
        self._settings = settings

    async def attempt(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        binding: AccountTransport,
        credentials: sender.SmtpCredentials,
        wire: bytes,
        started_at: str,
    ) -> AttemptResult:
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
            return AttemptResult.failed(error.code, error.message, auth=True)
        except sender.SmtpFailure as error:
            if error.uncertain:
                return self._uncertain(job, account, binding, started_at, error)
            self._failed(job, account, binding, started_at, error)
            if error.transient:
                return AttemptResult.deferred(error.code, error.message)
            return AttemptResult.failed(error.code, error.message)
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
        self._log.info(
            "smtp.accepted",
            job=job.id,
            message_id=job.message_id,
            duration_ms=result.accepted_ms,
        )
        return AttemptResult.sent()

    def _uncertain(
        self,
        job: Job,
        account: Account,
        binding: AccountTransport,
        started_at: str,
        error: sender.SmtpFailure,
    ) -> AttemptResult:
        self._recorder.record(
            job,
            account,
            binding,
            binding.kind.value,
            started_at,
            outcome="uncertain",
            accepted=None,
            code=error.code,
            message=error.message,
        )
        self._transports.mark_failure(
            binding,
            code=error.code,
            message=error.message,
            transient=False,
        )
        self._bus.publish(
            "transport.uncertain",
            {
                "job": job.id,
                "account": account.id,
                "binding": binding.id,
                "transport": binding.kind.value,
                "error_code": error.code,
            },
        )
        self._log.warning(
            "smtp.uncertain",
            job=job.id,
            account=account.id,
            code=error.code,
        )
        return AttemptResult.uncertain(error.code, error.message)

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

from __future__ import annotations

import asyncio

from downcroc.core.events import EventBus
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.outbound.attempts import AttemptRecorder
from downcroc.core.outbound.result import AttemptResult
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import OAuthClientNotFound
from downcroc.domain.jobs import Job
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.smtp.sender import SmtpCredentials
from downcroc.runtime.config.schema import OutboundSettings
from downcroc.runtime.logging.setup import EventLogger


class GmailDelivery:
    """Runs one Gmail API attempt through one binding."""

    def __init__(
        self,
        transports: TransportService,
        recorder: AttemptRecorder,
        clients: OAuthClientService,
        bus: EventBus,
        log: EventLogger,
        settings: OutboundSettings,
    ) -> None:
        self._transports = transports
        self._recorder = recorder
        self._clients = clients
        self._bus = bus
        self._log = log
        self._settings = settings

    async def attempt(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        binding: AccountTransport,
        credentials: SmtpCredentials,
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
        project_id = self._project_id(binding)
        try:
            result = await asyncio.to_thread(
                gmail_api.send,
                spec,
                account,
                credentials.access_token or "",
                wire,
                timeout_s=self._settings.api_timeout_s,
                project_id=project_id,
            )
        except gmail_api.GmailApiFailure as error:
            return self._failed(job, account, binding, started_at, error, project_id)
        self._recorder.record(
            job,
            account,
            binding,
            binding.kind.value,
            started_at,
            outcome="sent",
            accepted=True,
            provider_message_id=result.provider_message_id,
        )
        self._transports.mark_success(binding)
        self._bus.publish(
            "transport.sent",
            {
                "job": job.id,
                "account": account.id,
                "binding": binding.id,
                "transport": binding.kind.value,
                "provider_message_id": result.provider_message_id,
            },
        )
        self._bus.publish(
            "gmail.accepted",
            {
                "account": account.id,
                "binding": binding.id,
                "provider_message_id": result.provider_message_id,
            },
        )
        self._log.info(
            "gmail.accepted",
            job=job.id,
            account=account.id,
            binding=binding.id,
            provider_message_id=result.provider_message_id,
            duration_ms=result.accepted_ms,
        )
        return AttemptResult.sent(result.provider_message_id)

    def _failed(
        self,
        job: Job,
        account: Account,
        binding: AccountTransport,
        started_at: str,
        error: gmail_api.GmailApiFailure,
        project_id: str | None,
    ) -> AttemptResult:
        if error.uncertain:
            return self._uncertain(job, account, binding, started_at, error)
        deferred = error.transient or error.quota or error.code == "gmail_api_disabled"
        outcome = "deferred" if deferred else "failed"
        self._recorder.record(
            job,
            account,
            binding,
            binding.kind.value,
            started_at,
            outcome=outcome,
            accepted=False,
            code=error.code,
            message=error.message,
        )
        self._transports.mark_failure(
            binding,
            code=error.code,
            message=error.message,
            transient=error.transient,
            auth=error.auth,
            quota=error.quota,
            retry_after_s=error.retry_after_s,
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
        if error.code == "gmail_api_disabled":
            self._bus.publish(
                "gmail.api_disabled",
                {
                    "account": account.id,
                    "binding": binding.id,
                    "project_id": error.project_id or project_id,
                },
            )
        self._log.warning(
            "gmail.rejected",
            job=job.id,
            account=account.id,
            code=error.code,
            transient=error.transient,
            project_id=error.project_id or project_id,
        )
        if deferred:
            return AttemptResult.deferred(error.code, error.message)
        return AttemptResult.failed(error.code, error.message, auth=error.auth)

    def _uncertain(
        self,
        job: Job,
        account: Account,
        binding: AccountTransport,
        started_at: str,
        error: gmail_api.GmailApiFailure,
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
            "gmail.uncertain",
            job=job.id,
            account=account.id,
            binding=binding.id,
            code=error.code,
        )
        return AttemptResult.uncertain(error.code, error.message)

    def _project_id(self, binding: AccountTransport) -> str | None:
        if binding.oauth_client_id is None:
            return None
        try:
            return self._clients.get(binding.oauth_client_id).project_id
        except OAuthClientNotFound:
            return None

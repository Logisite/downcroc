from __future__ import annotations

from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.outbound.transports.gmail import GmailDelivery
from downcroc.core.outbound.transports.outcome import DeliveryOutcome
from downcroc.core.outbound.transports.smtp import SmtpDelivery
from downcroc.core.transports import TransportService
from downcroc.core.transports.limiter import TransportLimiter
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    OAuthFailed,
    OAuthUnavailable,
    SmtpUnavailable,
    VaultLocked,
)
from downcroc.domain.jobs import Job
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.mail.smtp import sender
from downcroc.runtime.logging.setup import EventLogger


class TransportDelivery:
    """Tries each healthy binding in order, never after a possible accept."""

    def __init__(
        self,
        transports: TransportService,
        credentials: CredentialResolver,
        smtp: SmtpDelivery,
        gmail: GmailDelivery,
        limiter: TransportLimiter,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._transports = transports
        self._credentials = credentials
        self._smtp = smtp
        self._gmail = gmail
        self._limiter = limiter
        self._bus = bus
        self._log = log

    async def deliver(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        wire: bytes,
        started_at: str,
        attempt_id: str,
        allowed_kinds: frozenset[TransportKind] | None = None,
    ) -> DeliveryOutcome:
        healthy = self._transports.usable(account)
        bindings = self._order(
            [
                binding
                for binding in healthy
                if allowed_kinds is None or binding.kind in allowed_kinds
            ]
        )
        if not bindings:
            for binding in healthy:
                self._log.warning(
                    "transport.seat_denied",
                    account=account.id,
                    binding=binding.id,
                    kind=binding.kind.value,
                    reason="slot_plan",
                )
            return DeliveryOutcome.deferred(
                None,
                "transport_unavailable",
                "the slot plan allows no healthy send transport",
            )
        busy = False
        last: DeliveryOutcome | None = None
        for binding in bindings:
            self._log.info(
                "transport.attempt",
                job=job.id,
                account=account.id,
                binding=binding.id,
                transport=binding.kind.value,
                attempt=attempt_id,
            )
            self._bus.publish(
                "transport.attempt",
                {
                    "job": job.id,
                    "account": account.id,
                    "binding": binding.id,
                    "transport": binding.kind.value,
                    "attempt": attempt_id,
                },
            )
            if not self._limiter.acquire(binding):
                busy = True
                continue
            try:
                outcome = await self._attempt(
                    job, account, spec, binding, wire, started_at, attempt_id
                )
            finally:
                self._limiter.release(binding)
            if outcome.status in {"sent", "uncertain", "reauth"}:
                return outcome
            last = outcome
        if last is not None:
            return last
        if busy:
            return DeliveryOutcome.deferred(
                None,
                "transport_busy",
                "every send transport is at capacity",
            )
        return DeliveryOutcome.deferred(
            None,
            "transport_unavailable",
            "no send transport could take the message",
        )

    async def _attempt(
        self,
        job: Job,
        account: Account,
        spec: ProviderSpec,
        binding: AccountTransport,
        wire: bytes,
        started_at: str,
        attempt_id: str,
    ) -> DeliveryOutcome:
        try:
            credentials = self._credentials_for(account, spec, binding)
        except AccountNeedsReauth:
            return DeliveryOutcome.reauth(
                "account_needs_reauth",
                "the mailbox must be reconnected",
            )
        except CredentialMissing, OAuthFailed, OAuthUnavailable, VaultLocked:
            return DeliveryOutcome.deferred(
                binding,
                "send_unavailable",
                "the send credential is not available",
            )
        except SmtpUnavailable:
            return DeliveryOutcome.deferred(
                binding,
                "smtp_unavailable",
                "the send credential could not be refreshed",
            )
        if binding.kind is TransportKind.GMAIL_API:
            result = await self._gmail.attempt(
                job,
                account,
                spec,
                binding,
                credentials,
                wire,
                started_at,
                attempt_id,
            )
        else:
            result = await self._smtp.attempt(
                job,
                account,
                spec,
                binding,
                credentials,
                wire,
                started_at,
                attempt_id,
            )
        if result.status == "sent":
            return DeliveryOutcome.sent(binding, result.provider_message_id)
        if result.status == "uncertain":
            return DeliveryOutcome.uncertain(
                binding, result.code or "send_uncertain", result.message or ""
            )
        if result.auth:
            return DeliveryOutcome.reauth(
                result.code or "account_needs_reauth",
                result.message or "the mailbox must be reconnected",
            )
        if result.status == "deferred":
            return DeliveryOutcome.deferred(
                binding,
                result.code or "send_deferred",
                result.message or "",
                result.retry_after_s,
            )
        return DeliveryOutcome.failed(
            binding,
            result.code or "send_failed",
            result.message or "",
        )

    def _credentials_for(
        self,
        account: Account,
        spec: ProviderSpec,
        binding: AccountTransport,
    ) -> sender.SmtpCredentials:
        client_id = binding.oauth_client_id
        if binding.kind is TransportKind.GMAIL_API:
            token = self._credentials.access_token(account, spec, client_id=client_id)
            return sender.SmtpCredentials(
                address=account.address,
                auth_kind=spec.auth_kind,
                access_token=token,
            )
        return self._credentials.resolve(account, spec, client_id=client_id)

    @staticmethod
    def _order(bindings: list[AccountTransport]) -> list[AccountTransport]:
        return sorted(
            bindings,
            key=lambda item: (-item.priority, 0 if item.seat else 1, item.id),
        )

from __future__ import annotations

from dataclasses import dataclass

from downcroc.core.credentials import CredentialResolver
from downcroc.core.inbound.gmail_target import project_id
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account
from downcroc.domain.jobs import Job
from downcroc.domain.messages import normalize_message_id
from downcroc.domain.providers import ProviderSpec
from downcroc.mail.gmail import read
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.send_attempts import SendAttemptRepo


@dataclass(frozen=True)
class _Read:
    value: str | None
    error: str | None = None


class DeliveredIdResolver:
    """Recovers the Message-ID Gmail actually stamped on a sent message.

    Gmail's ``messages.send`` overwrites the self-minted ``job.message_id`` with
    its own value on delivery. Follow-ups must reference the delivered id for
    the recipient to group them into one conversation. This resolver reads the
    real id back from Gmail using the opaque provider id stored on the send
    attempt, falling back to a Sent search by the minted id, and caches the
    result on the job. It never raises: failure returns None so callers fall
    back to the minted id.

    Every outcome is logged with the minted and delivered ids and the source,
    so a threading failure can be diagnosed from the logs alone.
    """

    def __init__(
        self,
        jobs: JobRepo,
        attempts: SendAttemptRepo,
        clients: OAuthClientService,
        accounts: AccountRepo,
        providers: ProviderRegistry,
        credentials: CredentialResolver,
        log: EventLogger,
        timeout_s: float,
    ) -> None:
        self._jobs = jobs
        self._attempts = attempts
        self._clients = clients
        self._accounts = accounts
        self._providers = providers
        self._credentials = credentials
        self._log = log
        self._timeout_s = timeout_s

    def recover(self, job: Job) -> str | None:
        """Recover and cache the delivered id for one job, or None on failure."""
        context = self._context(job)
        if context is None:
            self._log.info(
                "followup.delivered_id_failed",
                job=job.id,
                minted=job.message_id,
                detail="no credentials for account",
            )
            return None
        account, spec, token = context
        opaque = self._opaque_for(job.id)
        first = (
            self._via_opaque(spec, token, opaque, account) if opaque else _Read(None)
        )
        second = (
            self._via_search(spec, token, job.message_id, account)
            if first.value is None
            else _Read(None)
        )
        value = normalize_message_id(first.value or second.value)
        if value is None:
            self._log.info(
                "followup.delivered_id_failed",
                job=job.id,
                account=account.id,
                minted=job.message_id,
                opaque_error=first.error,
                search_error=second.error,
            )
            return None
        source = "opaque" if first.value else "search"
        self._jobs.set_delivered_message_id(job.id, value)
        self._log.info(
            "followup.delivered_id_recovered",
            job=job.id,
            account=account.id,
            minted=job.message_id,
            delivered=value,
            source=source,
        )
        return value

    def heal_account(
        self, account: Account, spec: ProviderSpec, token: str, limit: int = 100
    ) -> int:
        """Proactively recover delivered ids for an account's legacy sent jobs.

        Returns the number of ids recovered. Best-effort: recovery failures are
        logged and the job is retried on a later pass because its id stays NULL.
        """
        healed = 0
        for job in self._jobs.sent_without_delivered_id(account.id, limit):
            opaque = self._opaque_for(job.id)
            first = (
                self._via_opaque(spec, token, opaque, account)
                if opaque
                else _Read(None)
            )
            second = (
                self._via_search(spec, token, job.message_id, account)
                if first.value is None
                else _Read(None)
            )
            value = normalize_message_id(first.value or second.value)
            if value is None:
                self._log.info(
                    "followup.delivered_id_failed",
                    job=job.id,
                    account=account.id,
                    minted=job.message_id,
                    opaque_error=first.error,
                    search_error=second.error,
                )
                continue
            self._jobs.set_delivered_message_id(job.id, value)
            self._log.info(
                "followup.delivered_id_recovered",
                job=job.id,
                account=account.id,
                minted=job.message_id,
                delivered=value,
                source="opaque" if first.value else "search",
            )
            healed += 1
        return healed

    def capture(
        self,
        job: Job,
        opaque: str,
        account: Account,
        spec: ProviderSpec,
        token: str,
    ) -> str | None:
        """Read the delivered id by opaque id at send time and cache it."""
        result = self._via_opaque(spec, token, opaque, account)
        value = normalize_message_id(result.value)
        if value is None:
            self._log.info(
                "followup.delivered_id_failed",
                job=job.id,
                account=account.id,
                minted=job.message_id,
                opaque_error=result.error,
                source="send_readback",
            )
            return None
        self._jobs.set_delivered_message_id(job.id, value)
        self._log.info(
            "followup.delivered_id_captured",
            job=job.id,
            account=account.id,
            minted=job.message_id,
            delivered=value,
            source="send_readback",
        )
        return value

    def _context(self, job: Job) -> tuple[Account, ProviderSpec, str] | None:
        if job.account_id is None:
            return None
        try:
            account = self._accounts.get(job.account_id)
            spec = self._providers.get(account.provider)
            token = self._credentials.access_token(account, spec=spec)
        except Exception as error:  # noqa: BLE001 - recovery never blocks sending
            self._log.info(
                "followup.delivered_id_failed",
                job=job.id,
                detail=error.__class__.__name__,
                source="credentials",
            )
            return None
        return account, spec, token

    def _opaque_for(self, job_id: str) -> str | None:
        attempt = self._attempts.latest_for_job(job_id)
        if attempt is None or attempt.outcome not in ("sent", "sent_unconfirmed"):
            return None
        return attempt.provider_message_id

    def _via_opaque(
        self,
        spec: ProviderSpec,
        token: str,
        opaque: str,
        account: Account,
    ) -> _Read:
        try:
            message = read.get_message(
                spec,
                token,
                opaque,
                timeout_s=self._timeout_s,
                fmt="metadata",
                metadata_headers=("Message-ID",),
                project_id=project_id(self._clients, account),
            )
        except Exception as error:  # noqa: BLE001 - recovery never blocks sending
            return _Read(None, error.__class__.__name__)
        return _Read(message.message_id_header)

    def _via_search(
        self,
        spec: ProviderSpec,
        token: str,
        minted: str,
        account: Account,
    ) -> _Read:
        try:
            found = read.find_thread_id(
                spec,
                token,
                minted,
                timeout_s=self._timeout_s,
                project_id=project_id(self._clients, account),
            )
            if not found.page.messages:
                return _Read(None, "not_found")
            message = read.get_message(
                spec,
                token,
                found.page.messages[0].id,
                timeout_s=self._timeout_s,
                fmt="metadata",
                metadata_headers=("Message-ID",),
                project_id=project_id(self._clients, account),
            )
        except Exception as error:  # noqa: BLE001 - recovery never blocks sending
            return _Read(None, error.__class__.__name__)
        return _Read(message.message_id_header)

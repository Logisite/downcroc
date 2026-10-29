from __future__ import annotations

from downcroc.domain.accounts import Account
from downcroc.domain.attempts import SendAttempt
from downcroc.domain.jobs import Job
from downcroc.domain.transports import AccountTransport
from downcroc.runtime.clock import utc_now
from downcroc.runtime.ids import new_id
from downcroc.store.repositories.send_attempts import SendAttemptRepo


class AttemptRecorder:
    """Writes one send attempt for every delivery try."""

    def __init__(self, attempts: SendAttemptRepo) -> None:
        self._attempts = attempts

    def record(
        self,
        job: Job,
        account: Account,
        binding: AccountTransport | None,
        transport: str,
        started_at: str,
        *,
        outcome: str,
        accepted: bool | None,
        code: str | None = None,
        message: str | None = None,
        provider_message_id: str | None = None,
    ) -> None:
        self._attempts.create(
            SendAttempt(
                id=new_id("att"),
                job_id=job.id,
                account_id=account.id,
                binding_id=binding.id if binding is not None else None,
                transport=transport,
                started_at=started_at,
                finished_at=utc_now(),
                outcome=outcome,
                accepted=accepted,
                error_code=code,
                error_message=message,
                provider_message_id=provider_message_id,
                detail=None,
            )
        )

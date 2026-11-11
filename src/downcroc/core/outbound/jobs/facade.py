from __future__ import annotations

from downcroc.core.outbound.jobs.create import is_manual_batch
from downcroc.core.outbound.jobs.manual import ManualJobs
from downcroc.domain.errors import DomainError
from downcroc.domain.jobs import Job
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.jobs import JobRepo


class JobFacade:
    _jobs: JobRepo
    _manual: ManualJobs
    _log: EventLogger

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
        try:
            job = self._manual.create(
                account_id=account_id,
                recipient=recipient,
                recipient_name=recipient_name,
                subject=subject,
                text=text,
                html=html,
                batch_id=batch_id,
            )
        except DomainError as error:
            self._log.warning(
                "manual.job_rejected",
                account=account_id,
                batch=batch_id,
                reason=error.code,
            )
            raise
        self._log.info(
            "manual.job_created",
            job=job.id,
            account=job.account_id,
            batch=job.batch_id,
        )
        return job

    def hold_batch_id(self, job: Job) -> str | None:
        return None if is_manual_batch(job.batch_id) else job.batch_id

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

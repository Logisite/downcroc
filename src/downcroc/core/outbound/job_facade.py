from __future__ import annotations

from downcroc.domain.jobs import Job


class JobFacadeMixin:
    _jobs: object
    _manual: object

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
        return self._manual.create(
            account_id=account_id,
            recipient=recipient,
            recipient_name=recipient_name,
            subject=subject,
            text=text,
            html=html,
            batch_id=batch_id,
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

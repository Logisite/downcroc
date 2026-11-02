from __future__ import annotations

from downcroc.domain.accounts import Account
from downcroc.domain.batches import Batch
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo


def active_holds(
    runtime: RuntimeStateRepo,
    accounts: AccountRepo,
    jobs: JobRepo,
    *,
    account_id: str | None = None,
    batch: Batch | None = None,
    job_id: str | None = None,
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    state = runtime.get()
    if state.sending_paused_at is not None:
        found.append(
            {
                "level": "service",
                "since": state.sending_paused_at,
                "until": state.sending_paused_until,
                "reason": state.sending_paused_reason,
            }
        )
    if account_id is not None:
        account = accounts.get(account_id)
        if account.paused_at is not None:
            found.append(
                {
                    "level": "account",
                    "id": account.id,
                    "since": account.paused_at,
                    "reason": account.paused_reason,
                }
            )
    if batch is not None and batch.paused_at is not None:
        found.append(
            {
                "level": "batch",
                "id": batch.id,
                "since": batch.paused_at,
                "reason": batch.paused_reason,
            }
        )
    if job_id is not None:
        job = jobs.get(job_id)
        if job.paused_at is not None:
            found.append(
                {
                    "level": "job",
                    "id": job.id,
                    "since": job.paused_at,
                    "reason": job.paused_reason,
                }
            )
    return found


def paused_accounts(accounts: AccountRepo) -> list[Account]:
    return [account for account in accounts.list() if account.paused_at is not None]

from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.core.portability.reassign import Reassigner
from downcroc.core.portability.selection import TERMINAL, Selection
from downcroc.core.stats import StatsService
from downcroc.domain.batches import BatchState
from downcroc.domain.errors import (
    BatchStateConflict,
    JobInFlight,
    JobNotTerminal,
    JobStateConflict,
)
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batch_counters import BatchCounterRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo


class PortabilityService:
    def __init__(
        self,
        jobs: JobRepo,
        batches: BatchRepo,
        accounts: AccountRepo,
        counters: BatchCounterRepo,
        content: ContentStore,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._jobs = jobs
        self._batches = batches
        self._accounts = accounts
        self._counters = counters
        self._content = content
        self._stats = stats
        self._bus = bus
        self._log = log
        self._reassigner = Reassigner(jobs, batches, accounts, stats, bus, log)

    def cancel_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job.state is JobState.SENDING:
            raise JobInFlight(
                f"job {job_id} is in flight",
                hint="wait for the lease to expire and retry",
            )
        if job.state in {
            JobState.SENT,
            JobState.SENT_UNCONFIRMED,
            JobState.CANCELLED,
            JobState.FAILED,
        }:
            raise JobStateConflict(
                f"job {job_id} is {job.state.value}",
                hint="only a queued, held, or retry job can be cancelled",
            )
        cancelled = self._jobs.set_state(job_id, JobState.CANCELLED)
        self._stats.touch_batch(job.batch_id)
        self._log.info("job.cancelled", job=job.id, batch=job.batch_id)
        self._bus.publish("job.cancelled", {"id": job.id, "batch": job.batch_id})
        return cancelled

    def delete_job(self, job_id: str, *, force: bool, dry_run: bool) -> dict:
        job = self._jobs.get(job_id)
        if job.state is JobState.SENDING:
            raise JobInFlight(
                f"job {job_id} is in flight",
                hint="wait for the lease to expire and retry",
            )
        if dry_run:
            return {
                "job_id": job.id,
                "batch_id": job.batch_id,
                "state": job.state.value,
                "dry_run": True,
            }
        if job.state.value not in TERMINAL and not force:
            raise JobNotTerminal(
                f"job {job_id} is {job.state.value}",
                hint="cancel it first, or pass --force to delete it anyway",
            )
        size = self._content.discard(job.body_ref)
        self._jobs.delete(job.id)
        self._stats.touch_batch(job.batch_id)
        self._log.info(
            "job.deleted",
            job=job.id,
            batch=job.batch_id,
            state=job.state.value,
            bytes=size,
        )
        self._bus.publish("job.deleted", {"id": job.id, "batch": job.batch_id})
        return {
            "job_id": job.id,
            "batch_id": job.batch_id,
            "state": job.state.value,
            "bytes": size,
            "dry_run": False,
        }

    def deletion_preview(self, *, account_id: str | None, state: str | None) -> dict:
        if account_id is not None:
            counts = self._accounts.deletion_counts(account_id)
        else:
            jobs = self._jobs.select(states=[state] if state else None)
            counts = {"jobs": len(jobs)}
            for job in jobs:
                counts[job.state.value] = counts.get(job.state.value, 0) + 1
        blockers: list[str] = []
        if counts.get("sending"):
            blockers.append("job_in_flight")
        if counts.get("sent"):
            blockers.append("history_requires_force_history")
        if counts.get("jobs") and account_id is not None:
            blockers.append("account_in_use")
        return {
            "account_id": account_id,
            "state": state,
            "counts": counts,
            "blockers": blockers,
        }

    def reassign(
        self,
        *,
        from_account_id: str | None,
        to_account_id: str | None,
        selection: Selection,
        include_failed: bool,
        force: bool,
        dry_run: bool,
        pin: bool = False,
        unpin: bool = False,
    ) -> dict:
        return self._reassigner.reassign(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            selection=selection,
            include_failed=include_failed,
            force=force,
            dry_run=dry_run,
            pin=pin,
            unpin=unpin,
        )

    def reassign_batch(
        self,
        batch_id: str,
        *,
        to_account_id: str,
        states: list[str] | None,
        include_failed: bool,
        force: bool,
        dry_run: bool,
    ) -> dict:
        return self._reassigner.reassign_batch(
            batch_id,
            to_account_id=to_account_id,
            states=states,
            include_failed=include_failed,
            force=force,
            dry_run=dry_run,
        )

    def delete_batch(self, batch_id: str, *, dry_run: bool) -> dict:
        batch = self._batches.get(batch_id)
        if batch.state not in {BatchState.DONE, BatchState.CANCELLED}:
            raise BatchStateConflict(
                f"batch {batch_id} is {batch.state.value}",
                hint="cancel the batch before deleting it",
            )
        jobs = self._jobs.counts(batch_id)
        if dry_run:
            return {
                "batch_id": batch_id,
                "jobs": sum(jobs.values()),
                "dry_run": True,
            }
        deleted = self._batches.delete(batch_id)
        size = sum(self._content.discard(path) for path in deleted.bodies)
        self._counters.remove(batch_id)
        self._log.info(
            "batch.deleted",
            batch=batch_id,
            jobs=deleted.jobs,
            bytes=size,
        )
        self._bus.publish("batch.deleted", {"batch_id": batch_id})
        return {
            "batch_id": batch_id,
            "jobs": deleted.jobs,
            "bytes": size,
            "dry_run": False,
        }

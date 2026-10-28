from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.core.portability.selection import HISTORY, MOVABLE, TERMINAL, Selection
from downcroc.core.stats import StatsService
from downcroc.domain.accounts import AccountStatus
from downcroc.domain.batches import BatchState
from downcroc.domain.errors import (
    AccountArchived,
    AccountNotFound,
    AccountPending,
    BatchStateConflict,
    JobInFlight,
    JobNotTerminal,
    JobStateConflict,
    ReassignSameAccount,
    ReassignTargetInvalid,
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
        to_account_id: str,
        selection: Selection,
        include_failed: bool,
        force: bool,
        dry_run: bool,
    ) -> dict:
        target = self._target(to_account_id, from_account_id, force)
        wanted = self._states(selection.states, include_failed)
        filters = selection.as_filters()
        selected = self._jobs.select(
            job_ids=selection.job_ids,
            batch_ids=selection.batch_ids,
            account_id=from_account_id,
            states=wanted,
            created_since=filters["created_since"],
            created_until=filters["created_until"],
        )
        if selection.job_ids and from_account_id is not None:
            selected = [job for job in selected if job.account_id == from_account_id]
        self._refuse_in_flight(selected)
        move = [job for job in selected if job.state.value not in HISTORY]
        skipped = [
            {"id": job.id, "reason": f"state {job.state.value}"}
            for job in selected
            if job.state.value in HISTORY
        ]
        if dry_run:
            return {
                "jobs": len(move),
                "batches": len({job.batch_id for job in move}),
                "skipped": skipped,
                "dry_run": True,
            }
        touched = self._jobs.reassign(
            [job.id for job in move],
            target.id,
            reset_attempts=include_failed,
        )
        for batch_id in touched:
            self._repin(batch_id, from_account_id, target.id)
            self._stats.touch_batch(batch_id)
            self._log.info(
                "batch.reassigned",
                batch=batch_id,
                to=target.id,
                from_account=from_account_id,
            )
            self._bus.publish(
                "batch.reassigned", {"batch_id": batch_id, "account": target.id}
            )
        self._log.info(
            "job.reassigned",
            to=target.id,
            from_account=from_account_id,
            jobs=len(move),
            batches=len(touched),
        )
        self._bus.publish(
            "job.reassigned",
            {"account": target.id, "jobs": len(move), "batches": len(touched)},
        )
        return {
            "jobs": len(move),
            "batches": len(touched),
            "skipped": skipped,
            "dry_run": False,
        }

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
        batch = self._batches.get(batch_id)
        source = batch.account_id
        target = self._target(to_account_id, source, force)
        wanted = self._states(states, include_failed)
        selected = self._jobs.select(batch_ids=[batch_id], states=wanted)
        self._refuse_in_flight(selected)
        move = [job for job in selected if job.state.value not in HISTORY]
        skipped = [
            {"id": job.id, "reason": f"state {job.state.value}"}
            for job in selected
            if job.state.value in HISTORY
        ]
        if dry_run:
            return {
                "batch_id": batch_id,
                "jobs": len(move),
                "skipped": skipped,
                "dry_run": True,
            }
        self._jobs.reassign(
            [job.id for job in move],
            target.id,
            reset_attempts=include_failed,
        )
        self._batches.set_account(batch_id, target.id)
        self._stats.touch_batch(batch_id)
        self._log.info(
            "batch.reassigned",
            batch=batch_id,
            to=target.id,
            from_account=source,
            jobs=len(move),
        )
        self._bus.publish(
            "batch.reassigned", {"batch_id": batch_id, "account": target.id}
        )
        return {
            "batch_id": batch_id,
            "jobs": len(move),
            "skipped": skipped,
            "dry_run": False,
        }

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

    def _target(self, to_account_id: str, from_account_id: str | None, force: bool):
        if from_account_id is not None and to_account_id == from_account_id:
            raise ReassignSameAccount("the source and target account are the same")
        try:
            target = self._accounts.get(to_account_id)
        except AccountNotFound as error:
            raise ReassignTargetInvalid(
                f"no account {to_account_id}",
                hint="add the target account first",
            ) from error
        if target.archived_at is not None:
            raise AccountArchived(
                f"account {to_account_id} is archived",
                hint="unarchive the target account first",
            )
        if target.status is AccountStatus.PENDING and not force:
            raise AccountPending(
                f"account {to_account_id} is pending",
                hint="connect the target account, or pass --force",
            )
        return target

    @staticmethod
    def _states(states: list[str] | None, include_failed: bool) -> list[str]:
        wanted = list(states) if states else list(MOVABLE)
        if include_failed and "failed" not in wanted:
            wanted.append("failed")
        return wanted

    @staticmethod
    def _refuse_in_flight(jobs: list[Job]) -> None:
        sending = [job.id for job in jobs if job.state is JobState.SENDING]
        if sending:
            raise JobInFlight(
                f"{len(sending)} job(s) are in flight",
                hint="wait for the lease to expire and retry",
                fields={"jobs": ", ".join(sending[:5])},
            )

    def _repin(
        self, batch_id: str, from_account_id: str | None, to_account_id: str
    ) -> None:
        batch = self._batches.get(batch_id)
        if batch.account_id != from_account_id:
            return
        remaining = self._jobs.select(
            batch_ids=[batch_id], account_id=from_account_id, limit=1
        )
        if remaining:
            return
        self._batches.set_account(batch_id, to_account_id)

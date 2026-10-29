from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.core.portability.selection import HISTORY, MOVABLE, Selection
from downcroc.core.stats import StatsService
from downcroc.domain.accounts import AccountStatus
from downcroc.domain.errors import (
    AccountArchived,
    AccountNotFound,
    AccountPending,
    JobInFlight,
    ReassignSameAccount,
    ReassignTargetInvalid,
    SenderConflict,
)
from downcroc.domain.jobs import Job, JobState, SenderPolicy
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo


class Reassigner:
    def __init__(
        self,
        jobs: JobRepo,
        batches: BatchRepo,
        accounts: AccountRepo,
        stats: StatsService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._jobs = jobs
        self._batches = batches
        self._accounts = accounts
        self._stats = stats
        self._bus = bus
        self._log = log

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
        if pin and unpin:
            raise SenderConflict("choose --pin or --unpin, not both")
        if unpin and to_account_id is not None:
            raise SenderConflict(
                "--unpin does not take a target account",
                hint="drop the target when routing at send time",
            )
        if unpin:
            target = None
        elif to_account_id is None:
            raise SenderConflict(
                "a target account is required",
                hint="pass --to, or --unpin to route at send time",
            )
        else:
            target = self._target(
                to_account_id,
                from_account_id,
                force,
                allow_same=pin,
            )
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
        skipped = [
            {"id": job.id, "reason": f"state {job.state.value}"}
            for job in selected
            if job.state.value in HISTORY
        ]
        candidates = [job for job in selected if job.state.value not in HISTORY]
        movable = self._movable(candidates, pin=pin, unpin=unpin)
        skipped += [
            {"id": job.id, "reason": "already_auto"}
            for job in candidates
            if job.sender_policy is SenderPolicy.AUTO and job not in movable
        ]
        self._refuse_in_flight(movable)
        if dry_run:
            return self._result(movable, skipped, pin=pin, unpin=unpin, dry_run=True)
        ids = [job.id for job in movable]
        if unpin:
            touched = self._jobs.set_sender(
                ids,
                account_id=None,
                policy=SenderPolicy.AUTO.value,
                reset_attempts=include_failed,
            )
        elif pin:
            touched = self._jobs.set_sender(
                ids,
                account_id=target.id,
                policy=SenderPolicy.PINNED.value,
                reset_attempts=include_failed,
            )
        else:
            touched = self._jobs.reassign(
                ids,
                target.id,
                reset_attempts=include_failed,
            )
        event = "job.unpinned" if unpin else ("job.pinned" if pin else "job.reassigned")
        target_id = target.id if target is not None else None
        for batch_id in touched:
            self._sync_batch_sender(batch_id)
            self._stats.touch_batch(batch_id)
            self._log.info(
                "batch.reassigned",
                batch=batch_id,
                to=target_id,
                from_account=from_account_id,
            )
            self._bus.publish(
                "batch.reassigned",
                {"batch_id": batch_id, "account": target_id},
            )
        self._log.info(
            event,
            to=target_id,
            from_account=from_account_id,
            jobs=len(movable),
            batches=len(touched),
        )
        self._bus.publish(
            event,
            {
                "account": target_id,
                "jobs": len(movable),
                "batches": len(touched),
            },
        )
        return self._result(movable, skipped, pin=pin, unpin=unpin, dry_run=False)

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

    @staticmethod
    def _movable(
        candidates: list[Job],
        *,
        pin: bool,
        unpin: bool,
    ) -> list[Job]:
        if unpin:
            return [
                job for job in candidates if job.sender_policy is not SenderPolicy.AUTO
            ]
        if pin:
            return candidates
        return [job for job in candidates if job.sender_policy is SenderPolicy.PINNED]

    @staticmethod
    def _result(
        movable: list[Job],
        skipped: list[dict],
        *,
        pin: bool,
        unpin: bool,
        dry_run: bool,
    ) -> dict:
        return {
            "jobs": len(movable),
            "batches": len({job.batch_id for job in movable}),
            "skipped": skipped,
            "pinned": len(movable) if pin else 0,
            "unpinned": len(movable) if unpin else 0,
            "dry_run": dry_run,
        }

    def _target(
        self,
        to_account_id: str,
        from_account_id: str | None,
        force: bool,
        *,
        allow_same: bool = False,
    ):
        if (
            not allow_same
            and from_account_id is not None
            and to_account_id == from_account_id
        ):
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

    def _sync_batch_sender(self, batch_id: str) -> None:
        batch = self._batches.get(batch_id)
        accounts = self._jobs.pinned_accounts(batch_id)
        if not accounts:
            if batch.account_id is not None:
                self._batches.set_account(batch_id, None)
            return
        if len(accounts) == 1:
            only = next(iter(accounts))
            if batch.account_id != only:
                self._batches.set_account(batch_id, only)
            return
        if batch.account_id not in accounts:
            self._batches.set_account(batch_id, None)

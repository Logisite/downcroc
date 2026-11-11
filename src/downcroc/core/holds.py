from __future__ import annotations

from downcroc.core.capacity import CapacityService
from downcroc.core.events import EventBus
from downcroc.core.holds_impact import account_impact
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account
from downcroc.domain.batches import Batch
from downcroc.domain.errors import (
    BatchStateConflict,
    JobInFlight,
    JobStateConflict,
    PauseDurationInvalid,
    SendingPaused,
)
from downcroc.domain.jobs import Job, JobState, SenderPolicy
from downcroc.domain.runtime import RuntimeState
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo

ACTIVE = (JobState.QUEUED, JobState.RETRY_WAIT, JobState.AWAITING_APPROVAL)


class HoldsService:
    def __init__(
        self,
        settings: Settings,
        runtime: RuntimeStateRepo,
        accounts: AccountRepo,
        batches: BatchRepo,
        jobs: JobRepo,
        capacity: CapacityService,
        transports: TransportService,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._settings = settings
        self._runtime = runtime
        self._accounts = accounts
        self._batches = batches
        self._jobs = jobs
        self._capacity = capacity
        self._transports = transports
        self._bus = bus
        self._log = log

    def service_state(self) -> RuntimeState:
        return self._runtime.get()

    def status_block(self) -> dict[str, object]:
        state = self._runtime.get()
        held_jobs = sum(
            self._jobs.count(state=item.value)
            for item in (JobState.QUEUED, JobState.RETRY_WAIT, JobState.SENDING)
        )
        held_batches = sum(
            1
            for batch in self._batches.list(limit=10_000)
            if batch.state.value in {"sending", "awaiting_approval"}
        )
        return {
            "state": "paused" if state.paused else "running",
            "since": state.sending_paused_at,
            "until": state.sending_paused_until,
            "reason": state.sending_paused_reason,
            "held_jobs": held_jobs,
            "held_batches": held_batches,
        }

    def pause_service(
        self, reason: str | None, for_s: int | None
    ) -> tuple[RuntimeState, bool]:
        reason = self._reason(reason)
        if for_s is not None and not 1 <= for_s <= self._settings.dispatch.pause_max_s:
            raise PauseDurationInvalid(
                "the pause duration is out of range",
                hint=f"use 1..{self._settings.dispatch.pause_max_s} seconds",
            )
        before = self._runtime.get()
        until = utc_after(for_s) if for_s is not None else None
        after = self._runtime.pause(utc_now(), until, reason)
        changed = (
            not before.paused
            or before.sending_paused_reason != after.sending_paused_reason
            or before.sending_paused_until != after.sending_paused_until
        )
        if changed:
            self._bus.publish(
                "service.paused",
                {
                    "reason": after.sending_paused_reason,
                    "until": after.sending_paused_until,
                    "source": "manual",
                    "actor": "api",
                },
            )
            self._log.info(
                "service.paused",
                actor="api",
                reason=after.sending_paused_reason,
                until=after.sending_paused_until,
            )
            self._service_capacity_event("pause")
        return after, changed

    def resume_service(self, reason: str | None = None) -> tuple[RuntimeState, bool]:
        before = self._runtime.get()
        after = self._runtime.resume()
        changed = before.paused
        if changed:
            self._bus.publish(
                "service.resumed",
                {
                    "reason": self._reason(reason) or "manual",
                    "held_jobs": 0,
                    "held_batches": 0,
                },
            )
            self._log.info("service.resumed", reason=reason or "manual")
            self._service_capacity_event("resume")
        return after, changed

    def pause_account(
        self, account_id: str, reason: str | None
    ) -> tuple[Account, dict, bool]:
        account = self._accounts.get(account_id)
        changed = account.paused_at is None
        account = self._accounts.pause(account_id, utc_now(), self._reason(reason))
        impact = account_impact(
            account,
            settings=self._settings,
            jobs=self._jobs,
            transports=self._transports,
            capacity=self._capacity,
        )
        if changed:
            self._bus.publish(
                "account.paused",
                {
                    "account": account.id,
                    "reason": account.paused_reason,
                    "auto_jobs": impact["auto_jobs"],
                    "pinned_jobs": impact["held_pinned"],
                    "lost_lanes": impact["lost_lanes"],
                    "absorbed_by": impact["absorbed_by"],
                },
            )
            self._log.info(
                "account.paused", account=account.id, reason=account.paused_reason
            )
            self._capacity_event("pause", impact)
        return account, impact, changed

    def resume_account(
        self, account_id: str, reason: str | None = None
    ) -> tuple[Account, dict, bool]:
        account = self._accounts.get(account_id)
        changed = account.paused_at is not None
        account = self._accounts.resume(account_id)
        impact = account_impact(
            account,
            settings=self._settings,
            jobs=self._jobs,
            transports=self._transports,
            capacity=self._capacity,
        )
        if changed:
            self._bus.publish(
                "account.resumed",
                {
                    "account": account.id,
                    "reason": reason,
                    "held_jobs": impact["auto_jobs"],
                },
            )
            self._log.info("account.resumed", account=account.id, reason=reason)
            self._capacity_event("resume", impact)
        return account, impact, changed

    def pause_batch(self, batch_id: str, reason: str | None) -> tuple[Batch, bool]:
        batch = self._batches.get(batch_id)
        self._require_batch(batch)
        changed = batch.paused_at is None
        batch = self._batches.pause(batch_id, utc_now(), self._reason(reason))
        if changed:
            self._bus.publish(
                "batch.paused",
                {
                    "batch": batch.id,
                    "reason": batch.paused_reason,
                    "held_jobs": self._held_jobs(batch.id),
                },
            )
            self._log.info("batch.paused", batch=batch.id, reason=batch.paused_reason)
        return batch, changed

    def resume_batch(
        self, batch_id: str, reason: str | None = None
    ) -> tuple[Batch, bool]:
        batch = self._batches.get(batch_id)
        changed = batch.paused_at is not None
        batch = self._batches.resume(batch_id)
        if changed:
            self._bus.publish(
                "batch.resumed",
                {
                    "batch": batch.id,
                    "reason": reason,
                    "held_jobs": self._held_jobs(batch.id),
                },
            )
            self._log.info("batch.resumed", batch=batch.id, reason=reason)
        return batch, changed

    def pause_batches(self, reason: str | None) -> dict[str, object]:
        paused: list[str] = []
        skipped: list[dict[str, str]] = []
        for batch in self._batches.list(limit=10_000):
            if batch.state.value not in {"sending", "awaiting_approval"}:
                skipped.append({"id": batch.id, "reason": "batch_state_conflict"})
                continue
            self.pause_batch(batch.id, reason)
            paused.append(batch.id)
        return {"paused": paused, "skipped": skipped, "count": len(paused)}

    def resume_batches(self) -> dict[str, object]:
        paused: list[str] = []
        for batch in self._batches.list(limit=10_000):
            if batch.paused_at is None:
                continue
            self.resume_batch(batch.id)
            paused.append(batch.id)
        return {"paused": paused, "skipped": [], "count": len(paused)}

    def pause_job(self, job_id: str, reason: str | None) -> tuple[Job, bool]:
        job = self._jobs.get(job_id)
        if job.state is JobState.SENDING:
            raise JobInFlight(
                "the job is in flight", hint="wait for the attempt to settle"
            )
        if job.state not in ACTIVE:
            raise JobStateConflict("the job cannot be paused in this state")
        changed = job.paused_at is None
        try:
            job = self._jobs.pause(job_id, utc_now(), self._reason(reason))
        except ValueError as error:
            raise JobStateConflict("the job cannot be paused in this state") from error
        if changed:
            self._bus.publish(
                "job.paused",
                {"job": job.id, "batch": job.batch_id, "reason": job.paused_reason},
            )
            self._log.info("job.paused", job=job.id, batch=job.batch_id)
        return job, changed

    def resume_job(self, job_id: str, reason: str | None = None) -> tuple[Job, bool]:
        job = self._jobs.get(job_id)
        changed = job.paused_at is not None
        job = self._jobs.resume(job_id)
        if changed:
            self._bus.publish(
                "job.resumed", {"job": job.id, "batch": job.batch_id, "reason": reason}
            )
            self._log.info("job.resumed", job=job.id, batch=job.batch_id)
        return job, changed

    def held_pinned(self) -> int:
        total = 0
        for account in self._accounts.list():
            if account.paused_at is None:
                continue
            total += sum(
                1
                for job in self._jobs.list(account_id=account.id, limit=10_000)
                if job.sender_policy is SenderPolicy.PINNED and job.state in ACTIVE
            )
        return total

    def holds(
        self,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
        job_id: str | None = None,
    ) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        state = self._runtime.get()
        if state.paused:
            found.append(
                {
                    "level": "service",
                    "since": state.sending_paused_at,
                    "until": state.sending_paused_until,
                    "reason": state.sending_paused_reason,
                }
            )
        if account_id is not None:
            account = self._accounts.get(account_id)
            if account.paused_at is not None:
                found.append(
                    {
                        "level": "account",
                        "id": account.id,
                        "since": account.paused_at,
                        "reason": account.paused_reason,
                    }
                )
        if batch_id is not None:
            batch = self._batches.get(batch_id)
            if batch.paused_at is not None:
                found.append(
                    {
                        "level": "batch",
                        "id": batch.id,
                        "since": batch.paused_at,
                        "reason": batch.paused_reason,
                    }
                )
        if job_id is not None:
            job = self._jobs.get(job_id)
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

    def ensure_can_send(
        self,
        *,
        account_id: str | None = None,
        batch_id: str | None = None,
        job_id: str | None = None,
    ) -> None:
        active = self.holds(account_id=account_id, batch_id=batch_id, job_id=job_id)
        if not active:
            return
        first = active[0]
        raise SendingPaused(
            "sending is paused",
            hint="resume the hold and send again",
            fields={"scope": first["level"], "id": first.get("id")},
        )

    def _service_capacity_event(self, trigger: str) -> None:
        fleet = self._capacity.fleet()
        lanes = fleet.api_lanes + (1 if fleet.smtp_seats else 0)
        after = 0 if trigger == "pause" else lanes
        before = lanes if trigger == "pause" else 0
        self._bus.publish(
            "dispatch.capacity",
            {
                "trigger": trigger,
                "lanes_before": before,
                "lanes_after": after,
                "absorbed_by": [],
                "held_pinned": 0,
            },
        )

    def _capacity_event(self, trigger: str, impact: dict[str, object]) -> None:
        self._bus.publish(
            "dispatch.capacity",
            {
                "trigger": trigger,
                "lanes_before": impact["lanes_before"],
                "lanes_after": impact["lanes_after"],
                "absorbed_by": impact["absorbed_by"],
                "held_pinned": impact["held_pinned"],
            },
        )

    def _account_bindings(self, account: Account) -> list[dict[str, object]]:
        return [
            {"id": item.id, "kind": item.kind.value}
            for item in self._transports.bindings(account)
        ]

    @staticmethod
    def _transports_lanes(binding: dict[str, object]) -> int:
        return 1 if binding["kind"] == "smtp" else 2

    def _held_jobs(self, batch_id: str) -> int:
        return self._jobs.count(batch_id=batch_id, state=JobState.QUEUED.value)

    def _require_batch(self, batch: Batch) -> None:
        if batch.state.value not in {"sending", "awaiting_approval"}:
            raise BatchStateConflict("the batch cannot be paused in this state")

    def _reason(self, reason: str | None) -> str | None:
        if reason is None:
            return None
        cleaned = " ".join(reason.split())
        return cleaned[: self._settings.dispatch.pause_reason_max] or None

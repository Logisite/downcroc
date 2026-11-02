from __future__ import annotations

from downcroc.core.capacity_holds import active_holds
from downcroc.domain.accounts import Account
from downcroc.domain.batches import Batch
from downcroc.domain.jobs import Job, JobState, SenderPolicy
from downcroc.runtime.clock import utc_now
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.runtime_state import RuntimeStateRepo


class CapacityEtaMixin:
    _accounts: AccountRepo
    _batches: BatchRepo
    _jobs: JobRepo
    _runtime: RuntimeStateRepo

    def batch_eta(self, batch: Batch) -> dict[str, object]:
        counts = self._jobs.counts(batch.id)
        remaining = sum(
            counts.get(state.value, 0)
            for state in (
                JobState.QUEUED,
                JobState.SENDING,
                JobState.RETRY_WAIT,
            )
        )
        held = counts.get(JobState.AWAITING_APPROVAL.value, 0)
        account_ids = [batch.account_id] if batch.account_id else None
        capacity = self.selection(
            remaining,
            account_ids=account_ids,
            pinned=batch.account_id is not None,
        )
        holds = active_holds(
            self._runtime,
            self._accounts,
            self._jobs,
            account_id=batch.account_id,
            batch=batch,
        )
        state = self._batch_state(batch, remaining, held, capacity)
        if holds:
            state = "paused"
        finish = capacity["finish_at"]
        if state in {
            "awaiting_approval",
            "blocked",
            "paused",
            "done",
            "cancelled",
            "idle",
        }:
            finish = {"earliest": None, "latest": None}
        return {
            "state": state,
            "as_of": utc_now(),
            "remaining": remaining,
            "sendable": max(0, remaining - held),
            "held": held,
            "lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "serial": capacity["serial"],
            "duration_s": capacity["duration_s"],
            "finish_at": finish,
            "spills_window": capacity["spills_window"],
            "spills_day": capacity["spills_day"],
            "blocked_reason": (
                "paused"
                if state == "paused"
                else (capacity["blocked_reason"] if state == "blocked" else None)
            ),
            "blocked_by": holds[0]["level"] if holds else None,
            "holds": holds,
            "advice": capacity["advice"],
        }

    def job_eta(self, job: Job) -> dict[str, object] | None:
        if job.state not in (
            JobState.QUEUED,
            JobState.SENDING,
            JobState.RETRY_WAIT,
            JobState.AWAITING_APPROVAL,
        ):
            return None
        account_ids = [job.account_id] if job.account_id else None
        pinned = job.sender_policy is SenderPolicy.PINNED
        capacity = self.selection(
            1,
            account_ids=account_ids,
            pinned=pinned,
        )
        account = self._account(job.account_id)
        holds = active_holds(
            self._runtime,
            self._accounts,
            self._jobs,
            account_id=job.account_id,
            job_id=job.id,
        )
        return {
            "state": "paused" if holds else job.state.value,
            "blocked_by": holds[0]["level"] if holds else None,
            "holds": holds,
            "as_of": utc_now(),
            "next_attempt_at": job.next_attempt_at,
            "queue_position": 1,
            "queue_lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "sender_hint": account.address if account else None,
            "transport_hint": "smtp" if capacity["serial"] else "gmail_api",
            "finish_at": (
                {"earliest": None, "latest": None}
                if job.state is JobState.AWAITING_APPROVAL or holds
                else capacity["finish_at"]
            ),
            "blocked_reason": capacity["blocked_reason"],
        }

    def pending(self) -> dict[str, object]:
        total = sum(
            self._jobs.count(state=state.value)
            for state in (JobState.QUEUED, JobState.SENDING, JobState.RETRY_WAIT)
        )
        capacity = self.selection(total)
        held = active_holds(self._runtime, self._accounts, self._jobs)
        state = (
            "idle"
            if total == 0
            else (
                "paused"
                if held
                else ("blocked" if capacity["blocked_reason"] else "draining")
            )
        )
        return {
            "state": state,
            "remaining": total,
            "lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "serial": capacity["serial"],
            "smtp_queue": capacity["smtp_queue"],
            "smtp_waiting": capacity["smtp_waiting"],
            "finish_at": (
                {"earliest": None, "latest": None} if held else capacity["finish_at"]
            ),
            "blocked_reason": "paused" if held else capacity["blocked_reason"],
            "blocked_by": held[0]["level"] if held else None,
            "holds": held,
        }

    def _batch_state(
        self,
        batch: Batch,
        remaining: int,
        held: int,
        capacity: dict[str, object],
    ) -> str:
        if batch.state.value in {"done", "cancelled"}:
            return batch.state.value
        if capacity["blocked_reason"]:
            return "blocked"
        if held and remaining == held:
            return "awaiting_approval"
        if remaining <= 0:
            return "idle"
        return "draining"

    def _account(self, account_id: str | None) -> Account | None:
        if account_id is None:
            return None
        try:
            return self._accounts.get(account_id)
        except Exception:  # noqa: BLE001 - a deleted account is a missing hint
            return None

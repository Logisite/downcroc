from __future__ import annotations

import json

from downcroc.core.followups.planner import Planner
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import JobNotFound
from downcroc.domain.jobs import Job, JobState
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo

ACTIVE = frozenset(
    {
        JobState.AWAITING_APPROVAL.value,
        JobState.QUEUED.value,
        JobState.SENDING.value,
        JobState.RETRY_WAIT.value,
    }
)


class FollowUpStopper:
    def __init__(
        self,
        batches: BatchRepo,
        jobs: JobRepo,
        planner: Planner,
        log: EventLogger,
    ) -> None:
        self._batches = batches
        self._jobs = jobs
        self._planner = planner
        self._log = log
        self._skipped: set[tuple[str, str, str]] = set()

    def cancel_stopped(self) -> None:
        for job in self._jobs.pending_followups(limit=5000):
            reason = self._reason(job)
            if reason is None:
                continue
            changed = self._jobs.transition_one(
                job.id,
                from_state=job.state,
                to_state=JobState.CANCELLED,
            )
            if changed is None:
                continue
            self._log_skip(
                job.thread_root_job_id or job.id,
                job.step_key or "",
                reason,
            )
            self._finish_batch(job.batch_id)

    def _reason(self, job: Job) -> str | None:
        batch = self._batches.get(job.batch_id)
        if batch.parent_batch_id is None or job.thread_root_job_id is None:
            return None
        parent = self._batches.get(batch.parent_batch_id)
        if parent.state is BatchState.CANCELLED:
            return "batch_cancelled"
        try:
            root = self._jobs.get(job.thread_root_job_id)
        except JobNotFound:
            return None
        context = self._planner.context([root])
        signals = context.signals(root.id)
        options = _options(parent)
        if "reply" in options["stop_on"] and signals.reply:
            return "replied"
        if "bounce" in options["stop_on"] and signals.bounce:
            return "bounced"
        if options["suppress_replies"] and root.recipient in context.suppressed(
            root.account_id
        ):
            return "suppressed"
        return None

    def _finish_batch(self, batch_id: str) -> None:
        batch = self._batches.get(batch_id)
        if batch.state is not BatchState.SENDING and (
            batch.state is not BatchState.AWAITING_APPROVAL
        ):
            return
        counts = self._jobs.counts(batch_id)
        if ACTIVE & set(counts):
            return
        if counts.get(JobState.SENT.value, 0) > 0:
            state = BatchState.DONE
        else:
            state = BatchState.CANCELLED
        self._batches.set_state(batch_id, state)

    def _log_skip(self, job_id: str, step: str, reason: str) -> None:
        key = (job_id, step, reason)
        if key in self._skipped:
            return
        self._skipped.add(key)
        self._log.info(
            "followup.skipped",
            job=job_id,
            step=step,
            reason=reason,
        )


def _options(parent: Batch) -> dict[str, object]:
    try:
        raw = json.loads(parent.options_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "stop_on": raw.get("stop_on", ["reply", "bounce"]),
        "suppress_replies": raw.get("suppress_replies", True),
    }

from __future__ import annotations

from downcroc.core.followups.model import Skip, StepEvaluation
from downcroc.domain.batches import Batch
from downcroc.runtime.logging.setup import EventLogger


class FollowUpLog:
    def __init__(self, log: EventLogger) -> None:
        self._log = log
        self._planned_once: set[tuple[str, str]] = set()
        self._skipped: set[tuple[str, str, str]] = set()

    def planned_once(self, parent: Batch, evaluation: StepEvaluation) -> None:
        key = (parent.id, evaluation.step_key)
        if key in self._planned_once:
            return
        self._planned_once.add(key)
        self._log.info(
            "followup.planned",
            batch=parent.id,
            step=evaluation.step_key,
            candidates=0,
            replied=evaluation.replied,
            bounced=evaluation.bounced,
            suppressed=evaluation.suppressed,
            pending=evaluation.pending,
            not_due=evaluation.not_due,
        )

    def planned(
        self,
        parent: Batch,
        evaluation: StepEvaluation,
        allowed: int,
    ) -> None:
        self._planned_once.add((parent.id, evaluation.step_key))
        self._log.info(
            "followup.planned",
            batch=parent.id,
            step=evaluation.step_key,
            candidates=allowed,
            replied=evaluation.replied,
            bounced=evaluation.bounced,
            suppressed=evaluation.suppressed,
            pending=evaluation.pending,
            not_due=evaluation.not_due,
        )

    def skip_many(self, skipped: tuple[Skip, ...]) -> None:
        for item in skipped:
            self.skip(item.job_id, item.step_key, item.reason)

    def skip(self, job_id: str, step: str, reason: str) -> None:
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

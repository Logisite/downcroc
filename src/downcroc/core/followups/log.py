from __future__ import annotations

from downcroc.core.followups.model import Skip, StepEvaluation
from downcroc.domain.batches import Batch
from downcroc.runtime.logging import correlation
from downcroc.runtime.logging.setup import EventLogger


class FollowUpLog:
    def __init__(self, log: EventLogger) -> None:
        self._log = log
        self._planned_once: set[tuple[str, str]] = set()
        self._skipped: set[tuple[str, str, str]] = set()
        self._broken: set[tuple[str, str, str]] = set()
        self._rejected: set[tuple[str, str, str]] = set()

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
            broken=evaluation.broken,
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
            broken=evaluation.broken,
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

    def thread_broken(
        self,
        *,
        batch_id: str,
        step: str,
        parent: str,
        root: str,
        reason: str,
    ) -> None:
        key = (parent, step, reason)
        if key in self._broken:
            return
        self._broken.add(key)
        fields = {
            "parent": parent,
            "child": None,
            "root": root,
            "step": step,
            "reason": reason,
            "batch": batch_id,
        }
        self._log.warning("thread.broken", **fields)
        self._log.warning(
            "followup.thread_broken",
            correlation_id=correlation.current(),
            **fields,
        )

    def rejected(self, batch_id: str, step: str, code: str, detail: str) -> None:
        key = (batch_id, step, code)
        if key in self._rejected:
            return
        self._rejected.add(key)
        self._log.warning(
            "followup.rejected",
            batch=batch_id,
            step=step,
            code=code,
            detail=detail[:300],
            correlation_id=correlation.current(),
        )

    def thread_breaks(
        self, batch_id: str, step: str, skipped: tuple[Skip, ...]
    ) -> None:
        for item in skipped:
            if item.reason != "thread_broken":
                continue
            self.thread_broken(
                batch_id=batch_id,
                step=step,
                parent=item.job_id,
                root=item.job_id,
                reason=item.detail or "thread_broken",
            )

    def payload_ignored(self, batch_id: str, step: str, ignored) -> None:
        for item in ignored:
            self._log.warning(
                "payload_header_ignored",
                batch=batch_id,
                step=step,
                key=item.key,
                field=item.field,
            )

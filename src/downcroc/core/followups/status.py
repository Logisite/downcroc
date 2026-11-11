from __future__ import annotations

from dataclasses import dataclass, field

from downcroc.core.followups.model import StepEvaluation
from downcroc.domain.batches import BatchState
from downcroc.domain.followups import DeclarationState
from downcroc.domain.jobs import JobState

ACTIVE_JOB_STATES = {
    JobState.QUEUED.value,
    JobState.SENDING.value,
    JobState.RETRY_WAIT.value,
}
SENT_STATES = {JobState.SENT.value, JobState.SENT_UNCONFIRMED.value}


@dataclass(frozen=True)
class StepStatus:
    step: str
    kind: str
    state: str
    after_days: int
    when: str
    require_approval: bool
    version: int | None = None
    child_batch_id: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    detail: str | None = None


@dataclass(frozen=True)
class StatusReport:
    batch_id: str
    steps: tuple[StepStatus, ...]
    dry_run: bool = False
    changed: bool = False


def blocked_counts(evaluation: StepEvaluation) -> dict[str, int]:
    return {
        "candidates": len(evaluation.candidates)
        + evaluation.replied
        + evaluation.bounced
        + evaluation.suppressed
        + evaluation.pending
        + evaluation.not_due
        + evaluation.broken,
        "not_due": evaluation.not_due,
        "replied": evaluation.replied,
        "bounced": evaluation.bounced,
        "suppressed": evaluation.suppressed,
        "pending": evaluation.pending,
        "sent": 0,
        "failed": 0,
        "cancelled": 0,
        "awaiting": 0,
    }


def child_counts(job_counts: dict[str, int]) -> dict[str, int]:
    sent = sum(job_counts.get(state, 0) for state in SENT_STATES)
    failed = job_counts.get(JobState.FAILED.value, 0)
    cancelled = job_counts.get(JobState.CANCELLED.value, 0)
    awaiting = job_counts.get(JobState.AWAITING_APPROVAL.value, 0)
    return {
        "candidates": sum(job_counts.values()),
        "not_due": 0,
        "replied": 0,
        "bounced": 0,
        "suppressed": 0,
        "pending": sum(job_counts.get(state, 0) for state in ACTIVE_JOB_STATES),
        "sent": sent,
        "failed": failed,
        "cancelled": cancelled,
        "awaiting": awaiting,
    }


def derive_state(
    *,
    declaration_state: DeclarationState | None,
    child_state: BatchState | None,
    counts: dict[str, int],
    evaluation: StepEvaluation | None,
    deferred: bool,
    parent_sent: bool,
) -> str:
    if declaration_state is DeclarationState.RETIRED:
        return "retired"
    if child_state is not None:
        if child_state is BatchState.CANCELLED:
            return "cancelled_child"
        if counts.get("awaiting", 0) > 0:
            return "awaiting_approval"
        if counts.get("pending", 0) > 0:
            return "sending"
        if counts.get("sent", 0) > 0 and (
            counts.get("failed", 0) > 0 or counts.get("cancelled", 0) > 0
        ):
            return "partial"
        if counts.get("sent", 0) > 0:
            return "done"
        return "skipped"
    if declaration_state is DeclarationState.REMOVING:
        return "retired"
    if not parent_sent:
        return "parent_not_sent"
    if deferred:
        return "deferred"
    if evaluation is None:
        return "scheduled"
    if evaluation.broken > 0 and not evaluation.candidates:
        return "broken"
    if evaluation.candidates:
        return "pending"
    if evaluation.not_due:
        return "scheduled"
    return "skipped"

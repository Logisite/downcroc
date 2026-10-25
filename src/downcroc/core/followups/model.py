from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.jobs import Job


@dataclass(frozen=True)
class Content:
    subject: str
    text: str
    html: str | None
    attachments: tuple[str, ...] = ()
    source_dir: str = ""


@dataclass(frozen=True)
class Candidate:
    parent: Job
    anchor: Job
    step_key: str
    content: Content
    source_kind: str
    source_key: str | None
    source_index: int
    references: tuple[str, ...]


@dataclass(frozen=True)
class Skip:
    job_id: str
    step_key: str
    reason: str


@dataclass(frozen=True)
class StepEvaluation:
    step_key: str
    candidates: tuple[Candidate, ...] = ()
    skipped: tuple[Skip, ...] = ()
    replied: int = 0
    bounced: int = 0
    suppressed: int = 0
    pending: int = 0
    not_due: int = 0

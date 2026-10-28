from __future__ import annotations

from dataclasses import dataclass

from downcroc.domain.batches import Batch
from downcroc.domain.jobs import Job


@dataclass(frozen=True)
class PreviewMessage:
    key: str
    row: int | None
    email: str
    name: str | None
    subject: str
    text: str
    html: str | None
    attachments: tuple[str, ...]
    account_id: str | None


@dataclass(frozen=True)
class PreviewRouting:
    mode: str
    account_id: str | None
    counts: dict[str, int]
    unresolved: bool = False


@dataclass(frozen=True)
class PreviewFollowUp:
    key: str
    after_days: int
    when: str
    require_approval: bool


@dataclass(frozen=True)
class PreviewAttachments:
    count: int
    bytes: int


@dataclass(frozen=True)
class Preview:
    source_kind: str
    campaign_key: str
    campaign_name: str
    routing_mode: str
    messages: tuple[PreviewMessage, ...]
    ignored: tuple[str, ...]
    total: int = 0
    valid: int = 0
    sampled: int = 0
    sample_limit: int = 0
    warnings: tuple[str, ...] = ()
    routing: PreviewRouting | None = None
    followups: tuple[PreviewFollowUp, ...] = ()
    duplicates: int = 0
    attachments: PreviewAttachments | None = None


@dataclass(frozen=True)
class Sample:
    job_id: str
    key: str
    row: int | None
    email: str
    name: str | None
    subject: str
    text: str
    html: str | None
    attachments: tuple[str, ...]
    account_id: str


@dataclass(frozen=True)
class BatchDetail:
    batch: Batch
    counts: dict[str, int]
    jobs: tuple[Job, ...]
    samples: tuple[Sample, ...]
    reused: bool = False

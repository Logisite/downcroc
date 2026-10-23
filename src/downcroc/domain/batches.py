from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BatchKind(StrEnum):
    CAMPAIGN = "campaign"
    FOLLOW_UP = "follow_up"


class BatchState(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    SENDING = "sending"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Batch:
    id: str
    kind: BatchKind
    parent_batch_id: str | None
    name: str
    source_ref: str
    source_hash: str
    source_kind: str
    schema_version: str | None
    campaign_key: str | None
    producer_json: str
    template_ref: str | None
    account_id: str | None
    routing_json: str
    approval: str
    options_json: str
    state: BatchState
    sample_job_id: str | None
    samples: tuple[str, ...]
    ignored: tuple[str, ...]
    warnings: tuple[str, ...]
    created_at: str
    approved_at: str | None


@dataclass(frozen=True)
class NewBatch:
    id: str
    kind: BatchKind
    parent_batch_id: str | None
    name: str
    source_ref: str
    source_hash: str
    source_kind: str
    schema_version: str | None
    campaign_key: str | None
    producer_json: str
    template_ref: str | None
    account_id: str | None
    routing_json: str
    approval: str
    options_json: str
    state: BatchState
    samples: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: str = ""

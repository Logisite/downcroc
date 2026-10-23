from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from downcroc.core.batches import BatchDetail, Preview, PreviewMessage, Sample
from downcroc.domain.batches import Batch

from .jobs import JobOut


class BatchSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    template: str | None = Field(default=None, max_length=64)


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["one", "all"]


class BatchOut(BaseModel):
    id: str
    kind: str
    parent_batch_id: str | None
    name: str
    source_kind: str
    source_ref: str
    source_hash: str
    schema_version: str | None
    campaign_key: str | None
    template_ref: str | None
    account_id: str | None
    approval: str
    routing: dict[str, object]
    options: dict[str, object]
    state: str
    counts: dict[str, int]
    created_at: str
    approved_at: str | None

    @classmethod
    def of(cls, batch: Batch, counts: dict[str, int]) -> BatchOut:
        return cls(
            id=batch.id,
            kind=batch.kind.value,
            parent_batch_id=batch.parent_batch_id,
            name=batch.name,
            source_kind=batch.source_kind,
            source_ref=batch.source_ref,
            source_hash=batch.source_hash,
            schema_version=batch.schema_version,
            campaign_key=batch.campaign_key,
            template_ref=batch.template_ref,
            account_id=batch.account_id,
            approval=batch.approval,
            routing=json.loads(batch.routing_json or "{}"),
            options=json.loads(batch.options_json or "{}"),
            state=batch.state.value,
            counts=counts,
            created_at=batch.created_at,
            approved_at=batch.approved_at,
        )


class SampleOut(BaseModel):
    job_id: str
    key: str
    row: int | None
    email: str
    name: str | None
    subject: str
    text: str
    html: str | None
    attachments: list[str]
    account_id: str

    @classmethod
    def of(cls, sample: Sample) -> SampleOut:
        return cls(
            job_id=sample.job_id,
            key=sample.key,
            row=sample.row,
            email=sample.email,
            name=sample.name,
            subject=sample.subject,
            text=sample.text,
            html=sample.html,
            attachments=list(sample.attachments),
            account_id=sample.account_id,
        )


class BatchDetailOut(BatchOut):
    samples: list[SampleOut]
    recipients: list[JobOut]
    ignored: list[str]
    warnings: list[str]

    @classmethod
    def from_detail(cls, detail: BatchDetail) -> BatchDetailOut:
        base = BatchOut.of(detail.batch, detail.counts)
        return cls(
            **base.model_dump(),
            samples=[SampleOut.of(sample) for sample in detail.samples],
            recipients=[JobOut.of(job) for job in detail.jobs],
            ignored=list(detail.batch.ignored),
            warnings=list(detail.batch.warnings),
        )


class PreviewMessageOut(BaseModel):
    key: str
    row: int | None
    email: str
    name: str | None
    subject: str
    text: str
    html: str | None
    attachments: list[str]
    account_id: str | None

    @classmethod
    def of(cls, message: PreviewMessage) -> PreviewMessageOut:
        return cls(
            key=message.key,
            row=message.row,
            email=message.email,
            name=message.name,
            subject=message.subject,
            text=message.text,
            html=message.html,
            attachments=list(message.attachments),
            account_id=message.account_id,
        )


class PreviewOut(BaseModel):
    source_kind: str
    campaign_key: str
    campaign_name: str
    routing_mode: str
    messages: list[PreviewMessageOut]
    ignored: list[str]

    @classmethod
    def of(cls, preview: Preview) -> PreviewOut:
        return cls(
            source_kind=preview.source_kind,
            campaign_key=preview.campaign_key,
            campaign_name=preview.campaign_name,
            routing_mode=preview.routing_mode,
            messages=[PreviewMessageOut.of(message) for message in preview.messages],
            ignored=list(preview.ignored),
        )

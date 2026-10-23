from __future__ import annotations

import json
import random

from downcroc.core.batches.views import Sample
from downcroc.domain.batches import Batch
from downcroc.domain.errors import ContentMissing
from downcroc.domain.jobs import Job
from downcroc.store.content import ContentStore


def select(batch_id: str, job_ids: list[str], count: int) -> tuple[str, ...]:
    chosen = min(count, len(job_ids))
    if chosen == 0:
        return ()
    seed = int.from_bytes(batch_id.encode().ljust(8, b"0")[:8], "big")
    return tuple(random.Random(seed).sample(job_ids, chosen))


def previews(
    batch: Batch, jobs: list[Job], content: ContentStore
) -> tuple[Sample, ...]:
    if not batch.samples:
        return ()
    try:
        stored = json.loads(content.read_bytes(batch.source_ref))
    except ContentMissing, json.JSONDecodeError:
        return ()
    messages = {
        message.get("key"): message
        for message in stored.get("messages", [])
        if isinstance(message, dict)
    }
    by_id = {job.id: job for job in jobs}
    samples: list[Sample] = []
    for job_id in batch.samples:
        job = by_id.get(job_id)
        if job is None:
            continue
        source_key = job.source_key or f"r{job.source_index}"
        message = messages.get(source_key, {})
        recipient = message.get("to", {})
        samples.append(
            Sample(
                job_id=job.id,
                key=str(message.get("key", source_key)),
                row=job.source_index if batch.source_kind == "csv" else None,
                email=str(recipient.get("email", job.recipient)),
                name=recipient.get("name", job.recipient_name),
                subject=str(message.get("subject", job.subject)),
                text=str(message.get("text", "")),
                html=message.get("html"),
                attachments=tuple(message.get("attachments", [])),
                account_id=job.account_id,
            )
        )
    return tuple(samples)

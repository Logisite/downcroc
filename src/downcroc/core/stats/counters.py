from __future__ import annotations

import json

from downcroc.domain.errors import BatchNotFound
from downcroc.store.repositories.batch_counters import BatchCounterRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.messages import MessageRepo
from downcroc.store.repositories.replies import DEFAULT_REPLY_WINDOW_DAYS

ACTIVE = (
    "awaiting_approval",
    "queued",
    "sending",
    "retry_wait",
)


class BatchCounterUpdater:
    def __init__(
        self,
        batches: BatchRepo,
        jobs: JobRepo,
        messages: MessageRepo,
        counters: BatchCounterRepo,
    ) -> None:
        self._batches = batches
        self._jobs = jobs
        self._messages = messages
        self._counters = counters

    def touch(
        self,
        batch_id: str,
        *,
        suppressed_delta: int = 0,
        invalid_delta: int = 0,
    ) -> None:
        try:
            batch = self._batches.get(batch_id)
        except BatchNotFound:
            return
        raw = self._jobs.counts(batch_id)
        existing = self._counters.get(batch_id)
        totals = self._messages.batch_totals(
            batch_id, _reply_window(batch.options_json)
        )
        self._counters.replace(
            batch_id,
            queued=sum(raw.get(state, 0) for state in ACTIVE),
            sent=raw.get("sent", 0) + raw.get("sent_unconfirmed", 0),
            failed=raw.get("failed", 0),
            suppressed=(existing.suppressed if existing else 0) + suppressed_delta,
            invalid=(existing.invalid if existing else 0) + invalid_delta,
            inbound=totals.inbound,
            replies=totals.replies,
            late_replies=totals.late_replies,
            bounces=totals.bounces,
        )

    def refresh_all(self) -> int:
        refreshed = 0
        for batch in self._batches.list(limit=100_000):
            if not self._jobs.counts(batch.id):
                continue
            self.touch(batch.id)
            refreshed += 1
        return refreshed


def _reply_window(options_json: str) -> int:
    try:
        options = json.loads(options_json or "{}")
    except json.JSONDecodeError:
        return DEFAULT_REPLY_WINDOW_DAYS
    value = options.get("reply_window_days")
    if isinstance(value, int) and value >= 0:
        return value
    return DEFAULT_REPLY_WINDOW_DAYS

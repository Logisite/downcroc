from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime

from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import BatchNotFound
from downcroc.domain.jobs import Job
from downcroc.domain.policy import SendPolicy
from downcroc.runtime.clock import parse_utc, utc_after, utc_now


@dataclass
class Candidate:
    account: Account
    jobs: list[Job]
    remaining: int
    lanes: int


class DispatchHelpers:
    """Candidate eligibility, leasing, spacing, and cycle diagnostics."""

    def _can_send(self, account: Account) -> bool:
        return (
            account.status is AccountStatus.CONNECTED
            and self._policy.effective(account).enabled
            and account.credential_present
            and account.archived_at is None
        )

    def _batch_ready(
        self, job: Job, now: datetime, cache: dict[str, Batch | None]
    ) -> bool:
        if job.batch_id not in cache:
            try:
                cache[job.batch_id] = self._batches.get(job.batch_id)
            except BatchNotFound:
                cache[job.batch_id] = None
        batch = cache[job.batch_id]
        if batch is None or batch.state is not BatchState.SENDING:
            return False
        try:
            options = json.loads(batch.options_json or "{}")
        except json.JSONDecodeError:
            return True
        floor = options.get("not_before")
        if not floor:
            return True
        try:
            return parse_utc(str(floor)) <= now
        except ValueError:
            return True

    def _claim(self, account: Account, job: Job) -> Job | None:
        return self._jobs.claim(
            job.id,
            self._owner,
            utc_now(),
            utc_after(self._outbound_settings.lease_seconds),
        )

    def _weighted(self, candidates: list[Candidate]) -> Candidate:
        weights = [max(1, candidate.remaining) for candidate in candidates]
        return self._rng.choices(candidates, weights=weights, k=1)[0]

    def _apply_spacing(
        self, picked: list[tuple[Job, Account]], policies: dict[str, SendPolicy]
    ) -> None:
        seen: set[str] = set()
        for _, account in picked:
            if account.id in seen:
                continue
            seen.add(account.id)
            policy = policies[account.id]
            low = policy.jitter_min
            high = policy.jitter_max
            if high <= 0:
                self._next_allowed.pop(account.id, None)
                continue
            delay = self._rng.uniform(low, high)
            self._next_allowed[account.id] = time.monotonic() + delay
            self._log.debug("dispatch.spacing", delay_ms=round(delay * 1000))

    def _idle(self, due: int, window: int, allowance: int) -> None:
        if due == 0:
            reason = "nothing due"
        elif window >= due:
            reason = "window closed"
        elif allowance >= due:
            reason = "allowance spent"
        else:
            reason = "nothing due"
        self._log.debug("dispatch.idle", reason=reason)

    def _log_cycle(self, picked: int, sent: int, deferred: int, started: float) -> None:
        self._log.debug(
            "dispatch.cycle",
            picked=picked,
            sent=sent,
            deferred=deferred,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )

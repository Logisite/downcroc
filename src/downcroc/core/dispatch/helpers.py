from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime

from downcroc.core.transports.seats import SlotPlan
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.batches import Batch, BatchState
from downcroc.domain.errors import BatchNotFound
from downcroc.domain.jobs import Job
from downcroc.domain.policy import SendPolicy
from downcroc.domain.transports import TransportKind
from downcroc.runtime.clock import parse_utc, utc_after, utc_now


@dataclass
class Candidate:
    account: Account
    jobs: list[Job]
    remaining: int
    lanes: int
    has_smtp: bool = False
    has_api: bool = False
    pinned: bool = False
    kinds: frozenset[TransportKind] = frozenset()


class DispatchHelpers:
    """Candidate eligibility, leasing, spacing, and cycle diagnostics."""

    def _can_send(self, account: Account) -> bool:
        return (
            account.status is AccountStatus.CONNECTED
            and self._policy.effective(account).enabled
            and account.credential_present
            and account.archived_at is None
            and account.paused_at is None
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
        if (
            batch is None
            or batch.state is not BatchState.SENDING
            or batch.paused_at is not None
        ):
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
        """Least-recently-used with internal jitter, weighted by work left.

        Seat choice is round-robin in spirit: the account that has waited
        longest goes first, and jitter breaks ties so the order is not a fixed
        A-B-C loop. The jitter is internal and is not configurable.
        """
        turns = [
            self._transports.limiter.account_turn(candidate.account.id)
            for candidate in candidates
        ]
        oldest = min(turns)
        ready = [
            candidate for candidate, turn in zip(candidates, turns) if turn == oldest
        ]
        weights = [max(1, candidate.remaining) for candidate in ready]
        return self._rng.choices(ready, weights=weights, k=1)[0]

    def _limit_seats(self, candidates: list[Candidate]) -> list[Candidate]:
        """Apply the reassignable slot plan to the candidate set.

        The plan is derived from live config on every cycle. A seated account is
        SMTP-only; an unseated OAuth account is API-only; an unseated password
        account waits. Candidates with no usable mechanism are dropped.
        """
        if not candidates:
            return candidates
        plan = self._transports.pick_slots(
            pinned_ids=frozenset(
                candidate.account.id for candidate in candidates if candidate.pinned
            ),
            rng=self._rng,
        )
        keep: list[Candidate] = []
        for candidate in candidates:
            kinds = plan.kinds_for(
                candidate.account.id,
                has_smtp=candidate.has_smtp,
                has_api=candidate.has_api,
            )
            if not kinds:
                self._log.debug(
                    "dispatch.slot_waiting",
                    account=candidate.account.id,
                    position=(
                        plan.waiting.index(candidate.account.id) + 1
                        if candidate.account.id in plan.waiting
                        else 0
                    ),
                )
                continue
            bindings = self._transports.bindings(candidate.account)
            lanes = sum(
                self._transports.limiter.effective_limit(binding)
                for binding in bindings
                if binding.kind in kinds
            )
            if lanes <= 0:
                continue
            candidate.kinds = kinds
            candidate.lanes = lanes
            keep.append(candidate)
        self._notice_plan(plan)
        return keep

    def _notice_plan(self, plan: SlotPlan) -> None:
        signature = (plan.seats, plan.active_set, frozenset(plan.waiting))
        previous = getattr(self, "_plan_notice", None)
        if previous == signature:
            return
        self._plan_notice = signature
        previous_active = getattr(self, "_plan_active", frozenset())
        for position, account_id in enumerate(plan.active, start=1):
            if account_id not in previous_active:
                self._log.info(
                    "dispatch.slot_assigned",
                    account=account_id,
                    slot=position,
                    reason="rotation",
                )
        for account_id in previous_active - plan.active_set:
            self._log.info(
                "dispatch.slot_released",
                account=account_id,
                slot=0,
                reason="rotation",
            )
        self._plan_active = plan.active_set
        self._log.info(
            "dispatch.slot_plan",
            seats=plan.seats,
            active=list(plan.active),
            queue=list(plan.queue),
            waiting=list(plan.waiting),
            password_active=list(plan.password_active),
            oauth_active=list(plan.oauth_active),
            pinned_overflow=plan.pinned_overflow,
        )

    def _notice_seats(self) -> None:
        """Emit one tiered warning whenever the live seat width changes."""
        seats = self._dispatch.smtp_seats
        previous = getattr(self, "_seat_notice", None)
        if previous == seats:
            return
        self._seat_notice = seats
        if seats <= 1:
            return
        if seats <= 3:
            self._log.warning(
                "dispatch.smtp_seats_warning",
                seats=seats,
                reason="serial_rotation",
            )
            return
        self._log.error(
            "dispatch.smtp_seats_warning",
            seats=seats,
            reason="unsupported_risk",
        )

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

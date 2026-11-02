from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from downcroc.core.policy import PolicyResolver
from downcroc.core.transports import TransportService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.batches import Batch
from downcroc.domain.jobs import Job, JobState, SenderPolicy
from downcroc.domain.policy import SendPolicy
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import Settings
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.batches import BatchRepo
from downcroc.store.repositories.jobs import JobRepo
from downcroc.store.repositories.quota import QuotaRepo

ACTIVE = frozenset(
    {
        JobState.QUEUED,
        JobState.SENDING,
        JobState.RETRY_WAIT,
    }
)


@dataclass(frozen=True)
class Fleet:
    api_lanes: int
    smtp_seats: int
    accounts: list[Account]
    queue: tuple[str, ...] = ()
    waiting: tuple[str, ...] = ()
    password_accounts: int = 0
    oauth_accounts: int = 0
    oauth_api_only: int = 0
    password_waiting: int = 0

    @property
    def throughput(self) -> int:
        return max(0, self.api_lanes + (1 if self.smtp_seats else 0))


class CapacityService:
    """Capacity and ETA computed on read, never stored.

    SMTP is serial: a seat is one connection and only one SMTP send is in
    flight. ``smtp_seats`` widens the rotation, so N seats shorten the serial
    duration by N without ever claiming parallel SMTP sends.
    """

    def __init__(
        self,
        settings: Settings,
        accounts: AccountRepo,
        transports: TransportService,
        policy: PolicyResolver,
        quota: QuotaRepo,
        jobs: JobRepo,
        batches: BatchRepo,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._transports = transports
        self._policy = policy
        self._quota = quota
        self._jobs = jobs
        self._batches = batches

    # -- fleet -----------------------------------------------------------

    def fleet(self, account_ids: list[str] | None = None) -> Fleet:
        chosen = set(account_ids) if account_ids else None
        plan = self._transports.pick_slots(account_ids=account_ids)
        api_lanes = 0
        smtp_seats = len(plan.active)
        eligible: list[Account] = []
        password_accounts = 0
        oauth_accounts = 0
        oauth_api_only = 0
        password_waiting = 0
        for account in self._accounts.list():
            if chosen is not None and account.id not in chosen:
                continue
            if account.status is not AccountStatus.CONNECTED:
                continue
            if account.archived_at is not None:
                continue
            if not self._policy.effective(account).enabled:
                continue
            bindings = self._transports.bindings(account)
            if not bindings:
                continue
            password = self._transports.is_password(account)
            status = plan.status_for(
                account.id,
                has_smtp=any(binding.seat for binding in bindings),
                has_api=any(not binding.seat for binding in bindings),
            )
            if status == "none":
                continue
            eligible.append(account)
            if password:
                password_accounts += 1
                if status == "waiting":
                    password_waiting += 1
            else:
                oauth_accounts += 1
                if status == "api_only":
                    oauth_api_only += 1
            if status == "active":
                continue
            api_lanes += sum(
                self._transports.limiter.effective_limit(binding)
                for binding in bindings
                if not binding.seat
            )
        return Fleet(
            api_lanes=api_lanes,
            smtp_seats=smtp_seats,
            accounts=eligible,
            queue=plan.queue,
            waiting=plan.waiting,
            password_accounts=password_accounts,
            oauth_accounts=oauth_accounts,
            oauth_api_only=oauth_api_only,
            password_waiting=password_waiting,
        )

    # -- selection -------------------------------------------------------

    def selection(
        self,
        messages: int,
        *,
        account_ids: list[str] | None = None,
        pinned: bool = False,
        day: str | None = None,
    ) -> dict[str, object]:
        fleet = self.fleet(account_ids)
        messages = max(0, messages)
        policy = self._interval_policy(fleet.accounts)
        throughput = fleet.throughput
        blocked = None
        if messages > 0 and throughput <= 0:
            blocked = "no_binding"
            throughput = 1
        serial = fleet.api_lanes == 0 and fleet.smtp_seats > 0
        lanes = throughput if messages else 0
        seats = 1 if pinned else fleet.smtp_seats
        waves = max(1, math.ceil(messages / throughput)) if messages else 0
        duration_min = max(0, waves - 1) * policy.jitter_min
        duration_max = max(0, waves - 1) * policy.jitter_max
        earliest, latest, spills, spills_day = self._finish(
            duration_min, duration_max, policy, messages, fleet, day
        )
        advice = None
        if serial and messages > 1 and self._settings.dispatch.capacity_advice:
            advice = (
                "all eligible mailboxes are SMTP, so sends are serial; "
                "add a Gmail API binding to run API lanes in parallel"
            )
        return {
            "lanes": lanes,
            "seats": seats,
            "serial": serial,
            "smtp_queue": len(fleet.queue),
            "smtp_waiting": len(fleet.waiting),
            "password_accounts": fleet.password_accounts,
            "oauth_accounts": fleet.oauth_accounts,
            "oauth_api_only": fleet.oauth_api_only,
            "password_waiting": fleet.password_waiting,
            "messages": messages,
            "interval_s": {"min": policy.jitter_min, "max": policy.jitter_max},
            "duration_s": {"min": duration_min, "max": duration_max},
            "finish_at": {"earliest": earliest, "latest": latest},
            "bindings": self._kinds(fleet.accounts),
            "spills_window": spills,
            "spills_day": spills_day,
            "blocked_reason": blocked,
            "advice": advice,
        }

    # -- batch ETA -------------------------------------------------------

    def batch_eta(self, batch: Batch) -> dict[str, object]:
        counts = self._jobs.counts(batch.id)
        remaining = sum(counts.get(state.value, 0) for state in ACTIVE)
        held = counts.get(JobState.AWAITING_APPROVAL.value, 0)
        account_ids = [batch.account_id] if batch.account_id else None
        capacity = self.selection(
            remaining,
            account_ids=account_ids,
            pinned=batch.account_id is not None,
        )
        state = self._batch_state(batch, remaining, held, capacity)
        finish = capacity["finish_at"]
        if state in {"awaiting_approval", "blocked", "done", "cancelled", "idle"}:
            finish = {"earliest": None, "latest": None}
        return {
            "state": state,
            "as_of": utc_now(),
            "remaining": remaining,
            "sendable": max(0, remaining - held),
            "held": held,
            "lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "serial": capacity["serial"],
            "duration_s": capacity["duration_s"],
            "finish_at": finish,
            "spills_window": capacity["spills_window"],
            "spills_day": capacity["spills_day"],
            "blocked_reason": (
                capacity["blocked_reason"] if state == "blocked" else None
            ),
            "advice": capacity["advice"],
        }

    # -- job ETA ---------------------------------------------------------

    def job_eta(self, job: Job) -> dict[str, object] | None:
        if job.state not in ACTIVE and job.state is not JobState.AWAITING_APPROVAL:
            return None
        account_ids = [job.account_id] if job.account_id else None
        pinned = job.sender_policy is SenderPolicy.PINNED
        capacity = self.selection(
            1,
            account_ids=account_ids,
            pinned=pinned,
        )
        account = self._account(job.account_id)
        return {
            "state": job.state.value,
            "as_of": utc_now(),
            "next_attempt_at": job.next_attempt_at,
            "queue_position": 1,
            "queue_lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "sender_hint": account.address if account else None,
            "transport_hint": "smtp" if capacity["serial"] else "gmail_api",
            "finish_at": (
                {"earliest": None, "latest": None}
                if job.state is JobState.AWAITING_APPROVAL
                else capacity["finish_at"]
            ),
            "blocked_reason": capacity["blocked_reason"],
        }

    def pending(self) -> dict[str, object]:
        total = sum(self._jobs.count(state=state.value) for state in ACTIVE)
        capacity = self.selection(total)
        state = (
            "idle"
            if total == 0
            else ("blocked" if capacity["blocked_reason"] else "draining")
        )
        return {
            "state": state,
            "remaining": total,
            "lanes": capacity["lanes"],
            "seats": capacity["seats"],
            "serial": capacity["serial"],
            "smtp_queue": capacity["smtp_queue"],
            "smtp_waiting": capacity["smtp_waiting"],
            "finish_at": capacity["finish_at"],
            "blocked_reason": capacity["blocked_reason"],
        }

    # -- helpers ---------------------------------------------------------

    def _interval_policy(self, accounts: list[Account]) -> SendPolicy:
        if accounts:
            return self._policy.effective(accounts[0])
        all_accounts = self._accounts.list()
        if all_accounts:
            return self._policy.effective(all_accounts[0])
        return SendPolicy(
            daily_allowance=1,
            window_start=0,
            window_end=24,
            jitter_min=30,
            jitter_max=90,
            max_in_flight=1,
            enabled=True,
        )

    def _finish(
        self,
        duration_min: int,
        duration_max: int,
        policy: SendPolicy,
        messages: int,
        fleet: Fleet,
        day: str | None,
    ) -> tuple[str | None, str | None, bool, bool]:
        if messages <= 0:
            return None, None, False, False
        start = self._window_start(policy)
        earliest = start + timedelta(seconds=duration_min)
        latest = start + timedelta(seconds=duration_max)
        spills = latest.hour > policy.window_end
        if latest.date() > earliest.date():
            spills = True
        chosen_day = day or self._policy.day()
        allowance = 0
        for account in fleet.accounts:
            allowance += self._quota.available(
                account.id, chosen_day, self._policy.effective(account).daily_allowance
            )
        spills_day = messages > allowance
        if messages >= self._settings.dispatch.capacity_warn_messages:
            spills = spills or self._settings.dispatch.capacity_warn_on_window
        return earliest.isoformat(), latest.isoformat(), spills, spills_day

    @staticmethod
    def _window_start(policy: SendPolicy) -> datetime:
        now = datetime.now(UTC)
        if policy.window_start <= now.hour < policy.window_end:
            return now
        start = now.replace(hour=policy.window_start, minute=0, second=0, microsecond=0)
        if now.hour >= policy.window_end:
            start += timedelta(days=1)
        return start

    def _kinds(self, accounts: list[Account]) -> list[str]:
        kinds: set[str] = set()
        for account in accounts:
            for binding in self._transports.usable(account):
                kinds.add(binding.kind.value)
        return sorted(kinds)

    def _batch_state(
        self,
        batch: Batch,
        remaining: int,
        held: int,
        capacity: dict[str, object],
    ) -> str:
        if batch.state.value in {"done", "cancelled"}:
            return batch.state.value
        if capacity["blocked_reason"]:
            return "blocked"
        if held and remaining == held:
            return "awaiting_approval"
        if remaining <= 0:
            return "idle"
        return "draining"

    def _account(self, account_id: str | None) -> Account | None:
        if account_id is None:
            return None
        try:
            return self._accounts.get(account_id)
        except Exception:  # noqa: BLE001 - a deleted account is a missing hint
            return None

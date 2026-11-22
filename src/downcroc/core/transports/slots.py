from __future__ import annotations

import random
import time
from dataclasses import dataclass

from downcroc.core.accounts import AccountEligibility
from downcroc.core.policy import PolicyResolver
from downcroc.core.transports.health import BindingHealth
from downcroc.core.transports.limiter import TransportLimiter
from downcroc.core.transports.seats import SlotEntry, SlotPlan, choose_slots
from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind
from downcroc.domain.transports import TransportKind
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.config.schema import DispatchSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.quota import QuotaRepo


@dataclass(frozen=True)
class SeatDecision:
    """What a planning call should use, without committing it by default."""

    held: tuple[str, ...]
    release: str | None = None
    borrow: frozenset[str] | None = None


class SlotResolver:
    """Derives the active SMTP rotation from live config and live state.

    Planning is pure unless ``advance`` is set. Only dispatch advances the
    sticky holder, so read-only paths cannot rotate a seat by inspecting it.
    Config, allowance, health, and the last turn are read fresh on every call.
    """

    def __init__(
        self,
        accounts: AccountRepo,
        registry: ProviderRegistry,
        policy: PolicyResolver,
        quota: QuotaRepo,
        dispatch: DispatchSettings,
        health: BindingHealth,
        limiter: TransportLimiter,
        eligibility: AccountEligibility,
        log: EventLogger,
    ) -> None:
        self._accounts = accounts
        self._registry = registry
        self._policy = policy
        self._quota = quota
        self._dispatch = dispatch
        self._health = health
        self._limiter = limiter
        self._eligibility = eligibility
        self._log = log
        self._held: tuple[str, ...] = ()
        self._held_since = 0.0
        self._held_sends = 0
        self._held_batches: frozenset[str] = frozenset()

    def pick(
        self,
        *,
        day: str | None = None,
        pinned_ids: frozenset[str] = frozenset(),
        account_ids: list[str] | None = None,
        work: set[str] | None = None,
        rng: random.Random | None = None,
        advance: bool = False,
        batch_ids: frozenset[str] = frozenset(),
        active_batches: frozenset[str] | None = None,
        source: str = "query",
    ) -> SlotPlan:
        chosen = set(account_ids) if account_ids else None
        day = day or self._policy.day()
        rng = rng if rng is not None else random.Random(0)
        entries: list[SlotEntry] = []
        for account in self._accounts.list():
            if chosen is not None and account.id not in chosen:
                continue
            if not self._eligibility.sendable(account):
                continue
            policy = self._policy.effective(account)
            bindings = self._health.usable(account)
            has_smtp = any(binding.kind is TransportKind.SMTP for binding in bindings)
            has_api = any(
                binding.kind is TransportKind.GMAIL_API for binding in bindings
            )
            if not has_smtp and not has_api:
                continue
            entries.append(
                SlotEntry(
                    account_id=account.id,
                    password=self.is_password(account),
                    pinned=account.id in pinned_ids,
                    remaining=self._quota.available(
                        account.id, day, policy.daily_allowance
                    ),
                    turn=self._limiter.account_turn(account.id),
                    jitter=rng.random(),
                    has_smtp=has_smtp,
                    has_api=has_api,
                    smtp_ready=has_smtp,
                )
            )
        decision = self._decide(entries, advance, work, active_batches)
        planning = entries
        if decision.borrow is not None:
            working = [
                entry for entry in entries if entry.account_id in decision.borrow
            ]
            if working:
                planning = working
        plan = choose_slots(planning, self._dispatch.smtp_seats, held=decision.held)
        if advance:
            self._commit(plan, decision, batch_ids, source)
        return plan

    def _decide(
        self,
        entries: list[SlotEntry],
        advance: bool,
        work: set[str] | None,
        active_batches: frozenset[str] | None,
    ) -> SeatDecision:
        if not advance:
            return SeatDecision(self._held)
        if not self._dispatch.smtp_seat_sticky or not self._held:
            reason = "rotation" if self._held else "boot"
            return SeatDecision((), reason)
        ready = {
            entry.account_id
            for entry in entries
            if entry.has_smtp and entry.smtp_ready and entry.remaining > 0
        }
        if any(item not in ready for item in self._held):
            return SeatDecision((), "failover")
        if work and not (set(self._held) & work):
            working = [entry for entry in entries if entry.account_id in work]
            if not any(entry.has_api for entry in working):
                return SeatDecision((), borrow=frozenset(work))
        if self._dispatch.smtp_seat_max_s and (
            time.monotonic() - self._held_since >= self._dispatch.smtp_seat_max_s
        ):
            return SeatDecision((), "max_s")
        if self._dispatch.smtp_seat_max_sends and (
            self._held_sends >= self._dispatch.smtp_seat_max_sends
        ):
            return SeatDecision((), "max_sends")
        if (
            self._dispatch.smtp_seat_after_batch
            and active_batches is not None
            and self._held_batches
            and not (self._held_batches & active_batches)
        ):
            return SeatDecision((), "batch_drain")
        return SeatDecision(self._held)

    def _commit(
        self,
        plan: SlotPlan,
        decision: SeatDecision,
        batch_ids: frozenset[str],
        source: str,
    ) -> None:
        active = tuple(plan.active)
        release = decision.release
        if decision.borrow is not None:
            return
        if active == self._held and release in {None, "boot", "rotation"}:
            if not self._held_batches and batch_ids:
                self._held_batches = frozenset(batch_ids)
            return
        previous = self._held
        held_for = round(time.monotonic() - self._held_since, 3) if previous else 0
        sends = self._held_sends
        self._held = active
        self._held_since = time.monotonic()
        self._held_sends = 0
        self._held_batches = frozenset(batch_ids) if active else frozenset()
        self._log.info(
            "dispatch.smtp_seat",
            account=active[0] if active else None,
            released=previous[0] if previous else None,
            binding=None,
            reason=release or ("rotation" if previous else "boot"),
            held_for_s=held_for,
            sends=sends,
            source=source,
            order=list(active),
        )

    def note_send(self, account_id: str, transport: str) -> None:
        if transport != TransportKind.SMTP.value:
            return
        if account_id in self._held:
            self._held_sends += 1

    def allowed_kinds(
        self,
        account: Account,
        plan: SlotPlan | None = None,
        *,
        pinned: bool = False,
    ) -> frozenset[TransportKind]:
        if plan is None and pinned:
            plan = self.pick(pinned_ids=frozenset({account.id}))
        plan = plan or self.pick()
        bindings = self._health.usable(account)
        return plan.kinds_for(
            account.id,
            has_smtp=any(b.kind is TransportKind.SMTP for b in bindings),
            has_api=any(b.kind is TransportKind.GMAIL_API for b in bindings),
        )

    def status(self, account: Account, plan: SlotPlan | None = None) -> str:
        plan = plan or self.pick()
        bindings = self._health.usable(account)
        return plan.status_for(
            account.id,
            has_smtp=any(b.kind is TransportKind.SMTP for b in bindings),
            has_api=any(b.kind is TransportKind.GMAIL_API for b in bindings),
        )

    def is_password(self, account: Account) -> bool:
        return self._registry.get(account.provider).auth_kind is AuthKind.APP_PASSWORD

from __future__ import annotations

import random
import time

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


class SlotResolver:
    """Derives the active SMTP rotation from live config and live state.

    Nothing is cached: ``dispatch.smtp_seats``, allowance, health, and the last
    turn are read fresh so a config edit applies on the next cycle and a restart
    needs no rebuild step.
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
        self._held_picks = 0
        self._seat_reason = "boot"

    def pick(
        self,
        *,
        day: str | None = None,
        pinned_ids: frozenset[str] = frozenset(),
        account_ids: list[str] | None = None,
        rng: random.Random | None = None,
    ) -> SlotPlan:
        chosen = set(account_ids) if account_ids else None
        day = day or self._policy.day()
        rng = rng or random.Random()
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
        held = self._eligible_held(entries)
        if not held:
            self._seat_reason = "rotation" if self._held else "boot"
        plan = choose_slots(entries, self._dispatch.smtp_seats, held=held)
        self._remember(plan)
        return plan

    def _eligible_held(self, entries: list[SlotEntry]) -> tuple[str, ...]:
        if not self._dispatch.smtp_seat_sticky or not self._held:
            return ()
        ready = {
            entry.account_id
            for entry in entries
            if entry.has_smtp and entry.smtp_ready and entry.remaining > 0
        }
        if any(item not in ready for item in self._held):
            self._seat_reason = "failover"
            return ()
        if self._dispatch.smtp_seat_max_s and (
            time.monotonic() - self._held_since >= self._dispatch.smtp_seat_max_s
        ):
            self._seat_reason = "max_s"
            return ()
        if self._dispatch.smtp_seat_max_sends and (
            self._held_picks >= self._dispatch.smtp_seat_max_sends
        ):
            self._seat_reason = "max_sends"
            return ()
        self._held_picks += 1
        return self._held

    def _remember(self, plan: SlotPlan) -> None:
        active = tuple(plan.active)
        if active == self._held:
            return
        self._held = active
        self._held_since = time.monotonic()
        self._held_picks = 0
        self._log.info(
            "dispatch.smtp_seat",
            account=active[0] if active else None,
            binding=None,
            reason=self._seat_reason,
            held_for_s=0,
            sends=0,
            order=list(active),
        )

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

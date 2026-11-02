from __future__ import annotations

import random

from downcroc.core.policy import PolicyResolver
from downcroc.core.transports.health import BindingHealth
from downcroc.core.transports.limiter import TransportLimiter
from downcroc.core.transports.seats import SlotEntry, SlotPlan, choose_slots
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.providers import AuthKind
from downcroc.domain.transports import TransportKind
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.config.schema import DispatchSettings
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
    ) -> None:
        self._accounts = accounts
        self._registry = registry
        self._policy = policy
        self._quota = quota
        self._dispatch = dispatch
        self._health = health
        self._limiter = limiter

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
            if account.status is not AccountStatus.CONNECTED:
                continue
            if account.archived_at is not None:
                continue
            policy = self._policy.effective(account)
            if not policy.enabled:
                continue
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
        return choose_slots(entries, self._dispatch.smtp_seats)

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

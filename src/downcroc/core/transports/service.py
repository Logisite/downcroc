from __future__ import annotations

import random

from downcroc.core.accounts import AccountEligibility
from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.policy import PolicyResolver
from downcroc.core.transports import validation
from downcroc.core.transports.health import BindingHealth
from downcroc.core.transports.limiter import TransportLimiter
from downcroc.core.transports.probe import TransportProbe
from downcroc.core.transports.provision import Provisioner
from downcroc.core.transports.seats import SlotPlan
from downcroc.core.transports.slots import SlotResolver
from downcroc.domain.accounts import Account
from downcroc.domain.transports import (
    AccountTransport,
    TransportHealth,
    TransportKind,
)
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import DispatchSettings, OutboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.events import EventRepo
from downcroc.store.repositories.quota import QuotaRepo
from downcroc.store.repositories.transports import (
    TransportInvalid,
    TransportRepo,
)


class TransportService:
    def __init__(
        self,
        transports: TransportRepo,
        accounts: AccountRepo,
        registry: ProviderRegistry,
        credentials: CredentialResolver,
        clients: OAuthClientService,
        bus: EventBus,
        log: EventLogger,
        events: EventRepo,
        outbound: OutboundSettings,
        dispatch: DispatchSettings,
        policy: PolicyResolver,
        quota: QuotaRepo,
        eligibility: AccountEligibility,
    ) -> None:
        self._transports = transports
        self._accounts = accounts
        self._registry = registry
        self._credentials = credentials
        self._clients = clients
        self._bus = bus
        self._log = log
        self._events = events
        self._outbound = outbound
        self._dispatch = dispatch
        self._policy = policy
        self._quota = quota
        self._eligibility = eligibility
        self._health = BindingHealth(transports, bus, log, dispatch)
        self._limiter = TransportLimiter(dispatch)
        self._slots = SlotResolver(
            accounts,
            registry,
            policy,
            quota,
            dispatch,
            self._health,
            self._limiter,
            eligibility,
        )
        self._provision = Provisioner(transports, registry, clients, dispatch, self.add)

    @property
    def limiter(self) -> TransportLimiter:
        return self._limiter

    def ensure_defaults(self, account: Account) -> AccountTransport | None:
        return self._provision.defaults(account)

    def ensure_kind(
        self, account: Account, kind: TransportKind
    ) -> AccountTransport | None:
        return self._provision.kind(account, kind)

    def slot_status(
        self,
        account_id: str,
        plan: SlotPlan | None = None,
    ) -> str:
        return self._slots.status(self._accounts.get(account_id), plan)

    def is_password(self, account: Account) -> bool:
        return self._slots.is_password(account)

    def list(self, account_id: str) -> list[AccountTransport]:
        self._accounts.get(account_id)
        return self._transports.list_for_account(account_id)

    def get(self, account_id: str, binding_id: str) -> AccountTransport:
        self._accounts.get(account_id)
        return self._transports.get_for_account(account_id, binding_id)

    def add(
        self,
        account_id: str,
        *,
        kind: TransportKind,
        priority: int = 0,
        max_concurrency: int | None = None,
        rate_per_min: int | None = None,
        credential_ref: str | None = None,
        oauth_client_id: str | None = None,
    ) -> AccountTransport:
        account = self._accounts.get(account_id)
        spec = self._registry.get(account.provider)
        validation.validate_binding(kind, spec, max_concurrency, rate_per_min)
        if kind is TransportKind.SMTP and max_concurrency and max_concurrency > 1:
            raise TransportInvalid(
                "smtp is one connection per account",
                hint="add another mailbox as a seat, or raise dispatch.smtp_seats",
            )
        if kind is TransportKind.GMAIL_API:
            oauth_client_id = validation.resolve_client_id(
                self._clients, account, oauth_client_id, spec
            )
            if max_concurrency is None:
                max_concurrency = self._api_default(spec)
        elif max_concurrency is None:
            max_concurrency = 1
        now = utc_now()
        binding = AccountTransport(
            id=new_id("trn"),
            account_id=account.id,
            provider_id=account.provider,
            kind=kind,
            credential_ref=credential_ref or account.credential_key,
            oauth_client_id=oauth_client_id,
            enabled=True,
            priority=priority,
            max_concurrency=max_concurrency or 1,
            rate_per_min=rate_per_min,
            health=TransportHealth.READY,
            cooldown_until=None,
            last_error_code=None,
            last_error_message=None,
            last_success_at=None,
            created_at=now,
            updated_at=now,
        )
        created = self._transports.create(binding)
        self._bus.publish(
            "transport.binding_created",
            {
                "account": account.id,
                "binding": created.id,
                "kind": created.kind.value,
                "priority": created.priority,
            },
        )
        self._log.info(
            "transport.binding_created",
            account=account.id,
            binding=created.id,
            kind=created.kind.value,
            priority=created.priority,
        )
        if kind is TransportKind.SMTP and created.max_concurrency > 1:
            self._log.warning(
                "transport.smtp_concurrency",
                account=account.id,
                binding=created.id,
                max_concurrency=created.max_concurrency,
            )
        return created

    def update(
        self,
        account_id: str,
        binding_id: str,
        *,
        priority: int | None = None,
        max_concurrency: int | None = None,
        rate_per_min: int | None = None,
        enabled: bool | None = None,
    ) -> AccountTransport:
        binding = self.get(account_id, binding_id)
        changes: dict[str, object] = {}
        if priority is not None:
            changes["priority"] = priority
        if max_concurrency is not None:
            if max_concurrency < 1:
                raise TransportInvalid("max_concurrency must be at least 1")
            if binding.kind is TransportKind.SMTP and max_concurrency > 1:
                raise TransportInvalid(
                    "smtp is one connection per account",
                    hint="add another mailbox as a seat, or raise dispatch.smtp_seats",
                )
            changes["max_concurrency"] = max_concurrency
        if rate_per_min is not None:
            if binding.kind is TransportKind.SMTP:
                raise TransportInvalid("rate_per_min applies to gmail_api bindings")
            changes["rate_per_min"] = rate_per_min
        if enabled is not None:
            changes["enabled"] = enabled
            if not enabled:
                changes["health"] = TransportHealth.DISABLED.value
                changes["cooldown_until"] = None
            else:
                changes["health"] = TransportHealth.READY.value
                changes["cooldown_until"] = None
                changes["last_error_code"] = None
                changes["last_error_message"] = None
                self._health.forget(binding.id)
        if not changes:
            return binding
        changes["updated_at"] = utc_now()
        updated = self._transports.update(binding.id, changes)
        old = {key: _plain(getattr(binding, key)) for key in changes}
        new = {key: _plain(getattr(updated, key)) for key in changes}
        self._bus.publish(
            "transport.binding_updated",
            {
                "account": account_id,
                "binding": binding.id,
                "changed": sorted(changes),
                "old": old,
                "new": new,
            },
        )
        self._log.info(
            "transport.binding_updated",
            account=account_id,
            binding=binding.id,
            changed=sorted(changes),
            old=old,
            new=new,
        )
        return updated

    def remove(self, account_id: str, binding_id: str) -> AccountTransport:
        binding = self.get(account_id, binding_id)
        removed = self._transports.delete(binding.id)
        self._health.forget(binding.id)
        self._limiter.forget(binding.id)
        self._bus.publish(
            "transport.binding_removed",
            {
                "account": account_id,
                "binding": binding.id,
                "kind": binding.kind.value,
            },
        )
        self._log.info(
            "transport.binding_removed",
            account=account_id,
            binding=binding.id,
            kind=binding.kind.value,
        )
        return removed

    def select(self, account: Account) -> AccountTransport | None:
        ready = self.usable(account)
        if not ready:
            return None
        ready.sort(key=lambda item: (-item.priority, 0 if item.seat else 1, item.id))
        return ready[0]

    def usable(self, account: Account) -> list[AccountTransport]:
        return self._health.usable(account)

    def bindings(self, account: Account) -> list[AccountTransport]:
        """Healthy bindings, regardless of the slot plan."""
        return self._health.usable(account)

    def pick_slots(
        self,
        *,
        day: str | None = None,
        pinned_ids: frozenset[str] = frozenset(),
        account_ids: list[str] | None = None,
        rng: random.Random | None = None,
    ) -> SlotPlan:
        return self._slots.pick(
            day=day,
            pinned_ids=pinned_ids,
            account_ids=account_ids,
            rng=rng,
        )

    def allowed_kinds(
        self,
        account: Account,
        plan: SlotPlan | None = None,
        *,
        pinned: bool = False,
    ) -> frozenset[TransportKind]:
        return self._slots.allowed_kinds(account, plan, pinned=pinned)

    def lanes(self, account: Account) -> int:
        return sum(
            self._limiter.effective_limit(binding) for binding in self.usable(account)
        )

    def mark_success(self, binding: AccountTransport) -> AccountTransport:
        return self._health.mark_success(binding)

    def mark_failure(
        self,
        binding: AccountTransport,
        *,
        code: str,
        message: str,
        transient: bool,
        auth: bool = False,
        quota: bool = False,
        policy: bool = False,
        retry_after_s: int | None = None,
    ) -> AccountTransport:
        return self._health.mark_failure(
            binding,
            code=code,
            message=message,
            transient=transient,
            auth=auth,
            quota=quota,
            policy=policy,
            retry_after_s=retry_after_s,
        )

    def history(
        self,
        account_id: str,
        binding_id: str,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Recent state transitions for one binding, newest last."""
        binding = self.get(account_id, binding_id)
        events = self._events.recent("transport.", max(200, limit * 20))
        rows = [
            {
                "seq": event.seq,
                "type": event.type,
                "ts": event.ts,
                "reason": event.data.get("reason")
                or event.data.get("code")
                or event.data.get("changed"),
                "retry_s": event.data.get("retry_s"),
            }
            for event in events
            if event.data.get("binding") == binding.id
            and event.data.get("account") == binding.account_id
        ]
        return rows[-limit:]

    async def test(self, account_id: str, binding_id: str) -> dict[str, object]:
        probe = TransportProbe(
            self,
            self._accounts,
            self._registry,
            self._credentials,
            self._clients,
            self._outbound,
        )
        return await probe.test(account_id, binding_id)


def _plain(value: object) -> object:
    return getattr(value, "value", value)

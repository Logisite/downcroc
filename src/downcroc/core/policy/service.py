from __future__ import annotations

from dataclasses import replace

from downcroc.core.events import EventBus
from downcroc.core.policy import changes
from downcroc.core.policy.resolver import PolicyResolver
from downcroc.domain.policy import PolicyOverride, PolicyView
from downcroc.runtime.clock import utc_after
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.policy import SERVICE_SCOPE, PolicyRepo, account_scope


class PolicyService:
    def __init__(
        self,
        accounts: AccountRepo,
        overrides: PolicyRepo,
        resolver: PolicyResolver,
        bus: EventBus,
        log: EventLogger,
    ) -> None:
        self._accounts = accounts
        self._overrides = overrides
        self._resolver = resolver
        self._bus = bus
        self._log = log

    def account_view(self, account_id: str) -> PolicyView:
        account = self._accounts.get(account_id)
        resolution = self._resolver.resolve(account)
        return PolicyView(
            scope=account.id,
            values=resolution.values,
            sources=resolution.sources,
            expires_at=resolution.expires_at,
            permanent=account.policy,
            temporary=self._overrides.active(account_scope(account.id)),
        )

    def set_account(
        self,
        account_id: str,
        incoming: PolicyOverride,
        *,
        for_s: int | None = None,
    ) -> PolicyView:
        account = self._accounts.get(account_id)
        previous = self._resolver.resolve(account)
        if for_s is None:
            merged = _merge(account.policy, incoming)
            self._accounts.update_policy(account.id, merged)
            view = self.account_view(account.id)
            self._record(
                scope=account.id,
                target="account",
                old=changes.values(previous.values),
                new=changes.values(view.values),
            )
            self._resolved(account.id, previous.values, view)
            return view
        scope = account_scope(account.id)
        current = self._overrides.get(scope)
        merged = _merge(current, incoming)
        self._overrides.set(scope, merged, expires_at=utc_after(for_s))
        view = self.account_view(account.id)
        self._record(
            scope=account.id,
            target="account_temporary",
            old=changes.values(previous.values),
            new=changes.values(view.values),
            for_s=for_s,
        )
        self._resolved(account.id, previous.values, view)
        return view

    def clear_account(self, account_id: str) -> PolicyView:
        account = self._accounts.get(account_id)
        previous = self._resolver.resolve(account).values
        self._accounts.update_policy(account.id, PolicyOverride())
        self._overrides.clear(account_scope(account.id))
        view = self.account_view(account.id)
        self._cleared(account.id, "account", changes.values(account.policy), view)
        self._resolved(account.id, previous, view)
        return view

    def clear_account_temporary(self, account_id: str) -> PolicyView:
        account = self._accounts.get(account_id)
        previous = self._resolver.resolve(account).values
        previous_override = self._overrides.active(account_scope(account.id))
        self._overrides.clear(account_scope(account.id))
        view = self.account_view(account.id)
        self._cleared(
            account.id,
            "account_temporary",
            changes.values(previous_override or PolicyOverride()),
            view,
        )
        self._resolved(account.id, previous, view)
        return view

    def global_view(self) -> PolicyView:
        resolution = self._resolver.global_resolution()
        return PolicyView(
            scope="service",
            values=resolution.values,
            sources=resolution.sources,
            expires_at=resolution.expires_at,
            permanent=None,
            temporary=self._overrides.active(SERVICE_SCOPE),
        )

    def set_global(
        self, incoming: PolicyOverride, *, for_s: int | None = None
    ) -> PolicyView:
        previous = self._resolver.global_resolution().values
        current = self._overrides.get(SERVICE_SCOPE)
        merged = _merge(current, incoming)
        expires_at = utc_after(for_s) if for_s is not None else None
        self._overrides.set(SERVICE_SCOPE, merged, expires_at=expires_at)
        view = self.global_view()
        self._record(
            scope="service",
            target="service_temporary",
            old=changes.values(previous),
            new=changes.values(view.values),
            for_s=for_s,
        )
        self._resolved("service", previous, view)
        return view

    def clear_global(self) -> PolicyView:
        previous = self._resolver.global_resolution().values
        previous_override = self._overrides.active(SERVICE_SCOPE)
        self._overrides.clear(SERVICE_SCOPE)
        view = self.global_view()
        self._cleared(
            "service",
            "service_temporary",
            changes.values(previous_override or PolicyOverride()),
            view,
        )
        self._resolved("service", previous, view)
        return view

    def _resolved(self, scope: str, previous, view: PolicyView) -> None:
        changes.resolved(
            self._log,
            self._bus,
            scope=scope,
            previous=previous,
            current=view.values,
            source=view.sources.get("daily_allowance"),
        )

    def _record(
        self,
        *,
        scope: str,
        target: str,
        old: dict[str, object],
        new: dict[str, object],
        for_s: int | None = None,
    ) -> None:
        fields = {
            "scope": scope,
            "target": target,
            "fields": sorted(key for key in new if old.get(key) != new.get(key)),
            "old": old,
            "new": new,
            "for_s": for_s,
        }
        self._log.info("policy.changed", **fields)
        self._bus.publish("policy.changed", fields)

    def _cleared(
        self,
        scope: str,
        target: str,
        previous: dict[str, object],
        view: PolicyView,
    ) -> None:
        fields = {
            "scope": scope,
            "target": target,
            "previous": previous,
            "resolved": changes.values(view.values),
        }
        self._log.info("policy.cleared", **fields)
        self._bus.publish("policy.cleared", fields)


def _merge(current: PolicyOverride | None, incoming: PolicyOverride) -> PolicyOverride:
    if current is None:
        return replace(incoming, expires_at=None)
    values = current.values()
    values.update(incoming.values())
    return PolicyOverride(**values)

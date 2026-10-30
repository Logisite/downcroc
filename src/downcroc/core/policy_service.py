from __future__ import annotations

from dataclasses import replace

from downcroc.core.events import EventBus
from downcroc.core.policy import PolicyResolver
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
        if for_s is None:
            merged = _merge(account.policy, incoming)
            self._accounts.update_policy(account.id, merged)
            self._log.info(
                "policy.changed",
                scope=account.id,
                target="account",
                fields=sorted(incoming.values()),
            )
            self._changed("account", account.id, incoming)
            return self.account_view(account.id)
        scope = account_scope(account.id)
        current = self._overrides.get(scope)
        merged = _merge(current, incoming)
        self._overrides.set(scope, merged, expires_at=utc_after(for_s))
        self._log.info(
            "policy.changed",
            scope=account.id,
            target="account_temporary",
            fields=sorted(incoming.values()),
            for_s=for_s,
        )
        self._changed("account_temporary", account.id, incoming)
        return self.account_view(account.id)

    def clear_account(self, account_id: str) -> PolicyView:
        account = self._accounts.get(account_id)
        self._accounts.update_policy(account.id, PolicyOverride())
        self._overrides.clear(account_scope(account.id))
        self._log.info("policy.cleared", scope=account.id, target="account")
        self._changed("account", account.id, PolicyOverride())
        return self.account_view(account.id)

    def clear_account_temporary(self, account_id: str) -> PolicyView:
        account = self._accounts.get(account_id)
        self._overrides.clear(account_scope(account.id))
        self._log.info("policy.cleared", scope=account.id, target="account_temporary")
        self._changed("account_temporary", account.id, PolicyOverride())
        return self.account_view(account.id)

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
        current = self._overrides.get(SERVICE_SCOPE)
        merged = _merge(current, incoming)
        expires_at = utc_after(for_s) if for_s is not None else None
        self._overrides.set(SERVICE_SCOPE, merged, expires_at=expires_at)
        self._log.info(
            "policy.changed",
            scope="service",
            target="service_temporary",
            fields=sorted(incoming.values()),
            for_s=for_s,
        )
        self._changed("service", SERVICE_SCOPE, incoming)
        return self.global_view()

    def clear_global(self) -> PolicyView:
        self._overrides.clear(SERVICE_SCOPE)
        self._log.info("policy.cleared", scope="service", target="service_temporary")
        self._changed("service", SERVICE_SCOPE, PolicyOverride())
        return self.global_view()

    def _changed(self, target: str, scope: str, values: PolicyOverride) -> None:
        self._bus.publish(
            "policy.changed",
            {
                "target": target,
                "scope": scope,
                "fields": sorted(values.values()),
            },
        )


def _merge(current: PolicyOverride | None, incoming: PolicyOverride) -> PolicyOverride:
    if current is None:
        return replace(incoming, expires_at=None)
    values = current.values()
    values.update(incoming.values())
    return PolicyOverride(**values)

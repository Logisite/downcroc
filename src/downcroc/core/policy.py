from __future__ import annotations

from datetime import datetime, tzinfo

from downcroc.domain.accounts import Account
from downcroc.domain.policy import (
    POLICY_FIELDS,
    PolicyOverride,
    ResolvedPolicy,
    SendPolicy,
    tighten,
)
from downcroc.runtime.clock import zone_for
from downcroc.runtime.config.schema import Settings
from downcroc.store.repositories.policy import SERVICE_SCOPE, PolicyRepo, account_scope


class PolicyResolver:
    """Resolves the effective send policy at read time, never by syncing rows."""

    def __init__(self, settings: Settings, overrides: PolicyRepo) -> None:
        self._settings = settings
        self._overrides = overrides

    def now(self) -> datetime:
        return datetime.now(self.zone())

    def zone(self) -> tzinfo:
        return zone_for(self._settings.sending.timezone)

    def day(self, moment: datetime | None = None) -> str:
        return (moment or self.now()).date().isoformat()

    def global_values(self) -> SendPolicy:
        sending = self._settings.sending
        return SendPolicy(
            daily_allowance=sending.daily_allowance,
            window_start=sending.window_start,
            window_end=sending.window_end,
            jitter_min=sending.jitter_min,
            jitter_max=sending.jitter_max,
            max_in_flight=sending.max_in_flight,
            enabled=sending.enabled,
        )

    def global_resolution(self) -> ResolvedPolicy:
        values = self.global_values()
        sources = {field: "global" for field in POLICY_FIELDS}
        if self._settings.sending.enforcement_mode == "strict":
            return ResolvedPolicy(values, {field: "strict" for field in POLICY_FIELDS})
        override = self._overrides.active(SERVICE_SCOPE)
        if override is None:
            return ResolvedPolicy(values, sources)
        applied = override.apply(values)
        for field in override.values():
            sources[field] = "global_override"
        return ResolvedPolicy(applied, sources, override.expires_at)

    def resolve(
        self,
        account: Account,
        batch: PolicyOverride | None = None,
    ) -> ResolvedPolicy:
        global_resolution = self.global_resolution()
        values = global_resolution.values
        sources = dict(global_resolution.sources)
        expires_at = global_resolution.expires_at
        if self._settings.sending.enforcement_mode != "strict":
            permanent = account.policy
            values = permanent.apply(values)
            for field in permanent.values():
                sources[field] = "account"
            temporary = self._overrides.active(account_scope(account.id))
            if temporary is not None:
                values = temporary.apply(values)
                for field in temporary.values():
                    sources[field] = "account_override"
                expires_at = temporary.expires_at
        if batch is not None:
            tightened = tighten(values, batch)
            for field in batch.values():
                if getattr(tightened, field) != getattr(values, field):
                    sources[field] = "batch"
            values = tightened
        return ResolvedPolicy(values, sources, expires_at)

    def effective(
        self, account: Account, batch: PolicyOverride | None = None
    ) -> SendPolicy:
        return self.resolve(account, batch).values

    def service_override(self) -> PolicyOverride | None:
        return self._overrides.active(SERVICE_SCOPE)

    def account_override(self, account_id: str) -> PolicyOverride | None:
        return self._overrides.active(account_scope(account_id))

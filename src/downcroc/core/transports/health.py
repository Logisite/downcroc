from __future__ import annotations

from downcroc.core.events import EventBus
from downcroc.domain.accounts import Account
from downcroc.domain.transports import AccountTransport, TransportHealth
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import DispatchSettings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.transports import TransportRepo

_UNHEALTHY = frozenset(
    {
        TransportHealth.NEEDS_REAUTH,
        TransportHealth.DISABLED,
    }
)

_BACKOFF_CAP = 6


class BindingHealth:
    """Per-binding health, cool-down, and failure counters."""

    def __init__(
        self,
        transports: TransportRepo,
        bus: EventBus,
        log: EventLogger,
        dispatch: DispatchSettings,
    ) -> None:
        self._transports = transports
        self._bus = bus
        self._log = log
        self._dispatch = dispatch
        self._failures: dict[str, int] = {}

    def usable(self, account: Account) -> list[AccountTransport]:
        now = parse_utc(utc_now())
        usable: list[AccountTransport] = []
        for binding in self._transports.list_for_account(account.id):
            if not binding.enabled:
                continue
            if binding.health in _UNHEALTHY:
                continue
            if binding.cooldown_until is not None:
                try:
                    until = parse_utc(binding.cooldown_until)
                except ValueError:
                    until = now
                if until > now:
                    continue
                binding = self._transports.record_success(binding.id, utc_now())
            usable.append(binding)
        return usable

    def forget(self, binding_id: str) -> None:
        self._failures.pop(binding_id, None)

    def mark_success(self, binding: AccountTransport) -> AccountTransport:
        self.forget(binding.id)
        return self._transports.record_success(binding.id, utc_now())

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
        if auth:
            return self._reauth(binding, code, message)
        if quota:
            return self._quota(binding, code, message, retry_after_s)
        if policy:
            return self._policy(binding, code, message, retry_after_s)
        if not transient:
            return self._record(binding, binding.health, code, message, None)
        failures = self._failures.get(binding.id, 0) + 1
        self._failures[binding.id] = failures
        if failures < self._dispatch.network_cooldown_after:
            return self._record(binding, binding.health, code, message, None)
        extra = min(failures - self._dispatch.network_cooldown_after, _BACKOFF_CAP)
        retry_s = self._dispatch.network_cooldown_s * (2**extra)
        updated = self._record(
            binding,
            TransportHealth.COOLING_DOWN,
            code,
            message,
            utc_after(retry_s),
        )
        self._publish(
            "transport.cooldown",
            binding,
            reason=code,
            retry_s=retry_s,
        )
        return updated

    def _reauth(
        self,
        binding: AccountTransport,
        code: str,
        message: str,
    ) -> AccountTransport:
        updated = self._record(
            binding, TransportHealth.NEEDS_REAUTH, code, message, None
        )
        self._publish("transport.reauth", binding)
        return updated

    def _quota(
        self,
        binding: AccountTransport,
        code: str,
        message: str,
        retry_after_s: int | None,
    ) -> AccountTransport:
        retry_s = max(
            retry_after_s or 0,
            self._dispatch.quota_cooldown_s,
        )
        updated = self._record(
            binding,
            TransportHealth.QUOTA_EXHAUSTED,
            code,
            message,
            utc_after(retry_s),
        )
        self._publish("transport.quota", binding, retry_s=retry_s)
        return updated

    def _policy(
        self,
        binding: AccountTransport,
        code: str,
        message: str,
        retry_after_s: int | None,
    ) -> AccountTransport:
        retry_s = max(
            retry_after_s or 0,
            self._dispatch.network_cooldown_s,
        )
        updated = self._record(
            binding,
            TransportHealth.COOLING_DOWN,
            code,
            message,
            utc_after(retry_s),
        )
        self._publish(
            "transport.cooldown",
            binding,
            reason=code,
            retry_s=retry_s,
        )
        return updated

    def _record(
        self,
        binding: AccountTransport,
        health: TransportHealth,
        code: str,
        message: str,
        cooldown_until: str | None,
    ) -> AccountTransport:
        updated = self._transports.record_failure(
            binding.id,
            health=health,
            code=code,
            message=message,
            cooldown_until=cooldown_until,
            at=utc_now(),
        )
        old = {
            "health": binding.health.value,
            "cooldown_until": binding.cooldown_until,
            "last_error_code": binding.last_error_code,
        }
        new = {
            "health": updated.health.value,
            "cooldown_until": updated.cooldown_until,
            "last_error_code": updated.last_error_code,
        }
        self._bus.publish(
            "transport.binding_updated",
            {
                "account": updated.account_id,
                "binding": updated.id,
                "transport": updated.kind.value,
                "changed": ["health", "cooldown_until", "last_error_code"],
                "old": old,
                "new": new,
            },
        )
        self._log.info(
            "transport.binding_updated",
            account=updated.account_id,
            binding=updated.id,
            transport=updated.kind.value,
            changed=["health", "cooldown_until", "last_error_code"],
            old=old,
            new=new,
        )
        return updated

    def _publish(
        self,
        event: str,
        binding: AccountTransport,
        **fields: object,
    ) -> None:
        payload: dict[str, object] = {
            "account": binding.account_id,
            "binding": binding.id,
            "transport": binding.kind.value,
        }
        payload.update(fields)
        self._bus.publish(event, payload)
        self._log.warning(
            event,
            account=binding.account_id,
            binding=binding.id,
            transport=binding.kind.value,
            **fields,
        )

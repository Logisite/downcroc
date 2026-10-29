from __future__ import annotations

from downcroc.core.credentials import CredentialResolver
from downcroc.core.events import EventBus
from downcroc.core.transports.health import BindingHealth
from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.transports import (
    AccountTransport,
    TransportHealth,
    TransportKind,
)
from downcroc.mail.smtp import sender
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import DispatchSettings, OutboundSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
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
        bus: EventBus,
        log: EventLogger,
        outbound: OutboundSettings,
        dispatch: DispatchSettings,
    ) -> None:
        self._transports = transports
        self._accounts = accounts
        self._registry = registry
        self._credentials = credentials
        self._bus = bus
        self._log = log
        self._outbound = outbound
        self._health = BindingHealth(transports, bus, log, dispatch)

    def ensure_defaults(self, account: Account) -> AccountTransport | None:
        spec = self._registry.get(account.provider)
        existing = self._transports.list_for_account(account.id)
        if any(binding.kind is TransportKind.SMTP for binding in existing):
            return None
        if not spec.smtp_host or not spec.smtp_port:
            return None
        return self.add(
            account.id,
            kind=TransportKind.SMTP,
            priority=0,
            max_concurrency=1,
            rate_per_min=None,
            credential_ref=account.credential_key,
        )

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
        self._validate(kind, spec, max_concurrency, rate_per_min)
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
        self._bus.publish(
            "transport.binding_updated",
            {
                "account": account_id,
                "binding": binding.id,
                "changed": sorted(changes),
            },
        )
        self._log.info(
            "transport.binding_updated",
            account=account_id,
            binding=binding.id,
            changed=sorted(changes),
        )
        return updated

    def remove(self, account_id: str, binding_id: str) -> AccountTransport:
        binding = self.get(account_id, binding_id)
        removed = self._transports.delete(binding.id)
        self._health.forget(binding.id)
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

    def lanes(self, account: Account) -> int:
        return sum(
            1 if binding.seat else max(1, binding.max_concurrency)
            for binding in self.usable(account)
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
    ) -> AccountTransport:
        return self._health.mark_failure(
            binding,
            code=code,
            message=message,
            transient=transient,
            auth=auth,
            quota=quota,
        )

    async def test(self, account_id: str, binding_id: str) -> dict[str, object]:
        binding = self.get(account_id, binding_id)
        account = self._accounts.get(account_id)
        spec = self._registry.get(account.provider)
        if binding.kind is not TransportKind.SMTP:
            raise TransportInvalid(
                "gmail_api probes are not available yet",
                hint="authorize the mailbox and use the API binding",
            )
        self._credentials.ensure_unlocked()
        try:
            credentials = self._credentials.resolve(account, spec)
            await sender.test(
                spec,
                account,
                credentials,
                timeout_s=self._outbound.smtp_timeout_s,
            )
        except sender.SmtpFailure as error:
            updated = self.mark_failure(
                binding,
                code=error.code,
                message=error.message,
                transient=error.transient,
                auth=isinstance(error, sender.SmtpAuthFailure),
            )
            return {
                "ok": False,
                "code": error.code,
                "message": error.message,
                "health": updated.health.value,
            }
        updated = self.mark_success(binding)
        return {
            "ok": True,
            "code": None,
            "message": "the smtp session connected and authenticated",
            "health": updated.health.value,
        }

    def _validate(
        self,
        kind: TransportKind,
        spec: ProviderSpec,
        max_concurrency: int | None,
        rate_per_min: int | None,
    ) -> None:
        if kind is TransportKind.SMTP:
            if not spec.smtp_host or not spec.smtp_port:
                raise TransportInvalid(
                    "the provider has no smtp host",
                    hint="declare smtp_host and smtp_port first",
                )
            if rate_per_min is not None:
                raise TransportInvalid("rate_per_min applies to gmail_api bindings")
        if kind is TransportKind.GMAIL_API:
            if spec.id != "gmail":
                raise TransportInvalid(
                    "gmail_api bindings are only supported for gmail",
                    hint="use an smtp binding for this provider",
                )
            if spec.auth_kind is not AuthKind.OAUTH2:
                raise TransportInvalid("gmail_api requires an oauth2 provider")
        if max_concurrency is not None and max_concurrency < 1:
            raise TransportInvalid("max_concurrency must be at least 1")
        if rate_per_min is not None and rate_per_min < 1:
            raise TransportInvalid("rate_per_min must be at least 1")

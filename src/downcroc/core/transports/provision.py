from __future__ import annotations

from collections.abc import Callable

from downcroc.core.oauth_clients import OAuthClientService
from downcroc.domain.accounts import Account
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.config.schema import DispatchSettings
from downcroc.store.repositories.transports import TransportRepo

AddBinding = Callable[..., AccountTransport]


class Provisioner:
    """Creates the send mechanisms a mailbox is capable of.

    Capability is separate from capacity: every eligible mailbox may hold an
    SMTP binding, while ``dispatch.smtp_seats`` decides which bindings are
    active. OAuth mailboxes get both a Gmail API binding and an SMTP/XOAUTH2
    binding, so no app password and no manual binding step is required.
    """

    def __init__(
        self,
        transports: TransportRepo,
        registry: ProviderRegistry,
        clients: OAuthClientService,
        dispatch: DispatchSettings,
        add: AddBinding,
    ) -> None:
        self._transports = transports
        self._registry = registry
        self._clients = clients
        self._dispatch = dispatch
        self._add = add

    def defaults(self, account: Account) -> AccountTransport | None:
        spec = self._registry.get(account.provider)
        kinds = {
            binding.kind for binding in self._transports.list_for_account(account.id)
        }
        created: AccountTransport | None = None
        if spec.auth_kind is AuthKind.OAUTH2:
            if (
                TransportKind.GMAIL_API not in kinds
                and spec.api_configured
                and self.has_client(account)
            ):
                created = self._add(
                    account.id,
                    kind=TransportKind.GMAIL_API,
                    priority=0,
                    max_concurrency=self.api_default(spec),
                    rate_per_min=spec.api_rate_per_min,
                    credential_ref=account.credential_key,
                )
            if (
                TransportKind.SMTP not in kinds
                and spec.smtp_host
                and spec.smtp_port
                and self.has_client(account)
            ):
                created = self._add(
                    account.id,
                    kind=TransportKind.SMTP,
                    priority=0,
                    max_concurrency=1,
                    rate_per_min=None,
                    credential_ref=account.credential_key,
                    oauth_client_id=self._smtp_client(account, spec),
                )
            return created
        if TransportKind.SMTP in kinds:
            return None
        if not spec.smtp_host or not spec.smtp_port:
            return None
        return self._add(
            account.id,
            kind=TransportKind.SMTP,
            priority=0,
            max_concurrency=1,
            rate_per_min=None,
            credential_ref=account.credential_key,
            oauth_client_id=self._smtp_client(account, spec),
        )

    def kind(self, account: Account, kind: TransportKind) -> AccountTransport | None:
        existing = self._transports.list_for_account(account.id)
        if any(binding.kind is kind for binding in existing):
            return None
        spec = self._registry.get(account.provider)
        if kind is TransportKind.GMAIL_API:
            return self._add(
                account.id,
                kind=kind,
                priority=0,
                max_concurrency=self.api_default(spec),
                rate_per_min=spec.api_rate_per_min,
                credential_ref=account.credential_key,
            )
        return self._add(
            account.id,
            kind=kind,
            priority=0,
            max_concurrency=1,
            rate_per_min=None,
            credential_ref=account.credential_key,
            oauth_client_id=self._smtp_client(account, spec),
        )

    def _smtp_client(self, account: Account, spec: ProviderSpec) -> str | None:
        if spec.auth_kind is not AuthKind.OAUTH2:
            return None
        return self._clients.account_client(account)

    def has_client(self, account: Account) -> bool:
        spec = self._registry.get(account.provider)
        return (
            self._clients.account_client(account) is not None or spec.oauth_configured
        )

    def api_default(self, spec: ProviderSpec) -> int:
        return max(1, min(spec.api_max_concurrency, self._dispatch.api_max_concurrency))

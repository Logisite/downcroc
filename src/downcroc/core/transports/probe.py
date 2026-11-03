from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from downcroc.core.credentials import CredentialResolver
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.transports import validation
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.errors import AccountNeedsReauth, DomainError
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.mail.gmail import api as gmail_api
from downcroc.mail.smtp import sender
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.config.schema import OutboundSettings
from downcroc.store.repositories.accounts import AccountRepo

if TYPE_CHECKING:
    from downcroc.core.transports.service import TransportService


class TransportProbe:
    """Preflight checks for one binding, without touching the send path."""

    def __init__(
        self,
        transports: TransportService,
        accounts: AccountRepo,
        registry: ProviderRegistry,
        credentials: CredentialResolver,
        clients: OAuthClientService,
        outbound: OutboundSettings,
    ) -> None:
        self._transports = transports
        self._accounts = accounts
        self._registry = registry
        self._credentials = credentials
        self._clients = clients
        self._outbound = outbound

    async def test(self, account_id: str, binding_id: str) -> dict[str, object]:
        binding = self._transports.get(account_id, binding_id)
        account = self._accounts.get(account_id)
        spec = self._registry.get(account.provider)
        if account.status is AccountStatus.PENDING:
            return self._refused(
                binding,
                "account_pending",
                "connect the account before testing a transport",
            )
        if account.status is AccountStatus.NEEDS_REAUTH:
            return self._refused(
                binding,
                "account_needs_reauth",
                "the mailbox must be reconnected before testing a transport",
            )
        if binding.kind is TransportKind.GMAIL_API:
            return await self._test_api(binding, account, spec)
        return await self._test_smtp(binding, account, spec)

    async def _test_smtp(
        self,
        binding: AccountTransport,
        account: Account,
        spec: ProviderSpec,
    ) -> dict[str, object]:
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
            updated = self._transports.mark_failure(
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
        except DomainError as error:
            updated = self._transports.mark_failure(
                binding,
                code=error.code,
                message=error.message,
                transient=False,
                auth=True,
            )
            return {
                "ok": False,
                "code": error.code,
                "message": error.message,
                "health": updated.health.value,
            }
        updated = self._transports.mark_success(binding)
        return {
            "ok": True,
            "code": None,
            "message": "the smtp session connected and authenticated",
            "health": updated.health.value,
        }

    @staticmethod
    def _refused(
        binding: AccountTransport,
        code: str,
        message: str,
    ) -> dict[str, object]:
        return {
            "ok": False,
            "code": code,
            "message": message,
            "health": binding.health.value,
        }

    async def _test_api(
        self,
        binding: AccountTransport,
        account: Account,
        spec: ProviderSpec,
    ) -> dict[str, object]:
        self._credentials.ensure_unlocked()
        client = validation.client_of(self._clients, binding)
        project_id = client.project_id if client is not None else None
        try:
            token = self._credentials.access_token(
                account, spec, client_id=binding.oauth_client_id
            )
            profile = await asyncio.to_thread(
                gmail_api.profile,
                spec,
                token,
                timeout_s=self._outbound.api_timeout_s,
                project_id=project_id,
            )
        except AccountNeedsReauth as error:
            updated = self._transports.mark_failure(
                binding,
                code="account_needs_reauth",
                message="the mailbox must be reconnected",
                transient=False,
                auth=True,
            )
            return {
                "ok": False,
                "code": "account_needs_reauth",
                "message": error.message,
                "health": updated.health.value,
            }
        except gmail_api.GmailApiFailure as error:
            updated = self._transports.mark_failure(
                binding,
                code=error.code,
                message=error.message,
                transient=error.transient,
                auth=error.auth,
                quota=error.quota,
            )
            return {
                "ok": False,
                "code": error.code,
                "message": validation.api_message(error, project_id),
                "health": updated.health.value,
            }
        except DomainError as error:
            updated = self._transports.mark_failure(
                binding,
                code=error.code,
                message=error.message,
                transient=False,
                auth=True,
            )
            return {
                "ok": False,
                "code": error.code,
                "message": error.message,
                "health": updated.health.value,
            }
        updated = self._transports.mark_success(binding)
        return {
            "ok": True,
            "code": None,
            "message": f"the gmail api answered for {profile.address}",
            "health": updated.health.value,
        }

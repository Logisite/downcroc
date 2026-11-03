from __future__ import annotations

from downcroc.core.accounts_login import AccountLoginMixin
from downcroc.core.events import EventBus
from downcroc.core.inbound import InboundService
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.stats import StatsService
from downcroc.core.transports import TransportService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.attempts import ConnectAttempt
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    ImapAuthFailed,
    InvalidAccount,
    ProviderAuthMismatch,
    VaultLocked,
)
from downcroc.domain.policy import PolicyOverride
from downcroc.domain.providers import AuthKind
from downcroc.domain.secrets import secret_key
from downcroc.domain.transports import TransportKind
from downcroc.domain.validators import validate_account
from downcroc.providers.oauth.flow import OAuthFlow
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import TokenManager
from downcroc.runtime.clock import utc_now
from downcroc.runtime.config.schema import ConnectSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.content import ContentStore
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.attempts import AttemptRepo


class AccountsService(AccountLoginMixin):
    def __init__(
        self,
        accounts: AccountRepo,
        bus: EventBus,
        log: EventLogger,
        registry: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        attempts: AttemptRepo,
        settings: ConnectSettings,
        inbound: InboundService,
        content: ContentStore,
        stats: StatsService,
        transports: TransportService,
        clients: OAuthClientService,
    ) -> None:
        self._accounts = accounts
        self._bus = bus
        self._log = log
        self._registry = registry
        self._vault = vault
        self._tokens = tokens
        self._settings = settings
        self._inbound = inbound
        self._content = content
        self._stats = stats
        self._transports = transports
        self._clients = clients
        self._attempt_transports: dict[str, TransportKind] = {}
        self._flow = OAuthFlow(attempts, settings, log, self._complete_oauth)

    def create(self, provider: str, address: str, label: str) -> Account:
        provider, address, label = validate_account(provider, address, label)
        if not self._registry.has(provider):
            raise InvalidAccount(
                "the provider is not declared",
                hint="add it to providers.toml or providers.d",
                fields={"provider": provider},
            )
        account = Account(
            id=new_id("acct"),
            provider=provider,
            address=address,
            label=label,
            status=AccountStatus.PENDING,
            credential_present=False,
            created_at=utc_now(),
            last_verified_at=None,
            policy=PolicyOverride(),
        )
        self._accounts.create(account)
        self._transports.ensure_defaults(account)
        self._bus.publish("account.added", {"id": account.id})
        self._log.info("account.created", account=account.id, provider=provider)
        return account

    def list(self, *, archived: bool = False) -> list[Account]:
        if archived:
            return self._accounts.list(archived_only=True)
        return self._accounts.list()

    def get(self, account_id: str) -> Account:
        return self._accounts.get(account_id)

    def delete(
        self,
        account_id: str,
        *,
        reassign_to: str | None = None,
        force_jobs: bool = False,
        force_history: bool = False,
    ) -> dict:
        result = self._accounts.delete(
            account_id,
            reassign_to=reassign_to,
            force_jobs=force_jobs,
            force_history=force_history,
        )
        self._flow.stop_for_account(account_id)
        self._inbound.account_removed(account_id)
        for path in result.bodies:
            self._content.discard(path)
        for batch_id in result.batches:
            self._stats.touch_batch(batch_id)
        try:
            self._vault.delete_account_secrets(account_id)
        except VaultLocked:
            pass
        self._bus.publish("account.deleted", {"id": account_id})
        self._log.info(
            "account.deleted",
            account=account_id,
            reassigned=result.reassigned,
            jobs=result.deleted_jobs,
        )
        return {
            "account_id": account_id,
            "reassigned": result.reassigned,
            "deleted_jobs": result.deleted_jobs,
        }

    def archive(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account.archived_at is not None:
            return account
        updated = self._accounts.archive(account_id, utc_now())
        self._flow.stop_for_account(account_id)
        self._inbound.account_changed(account_id, False)
        self._bus.publish("account.archived", {"id": account_id})
        self._log.info("account.archived", account=account_id)
        return updated

    def unarchive(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account.archived_at is None:
            return account
        updated = self._accounts.unarchive(account_id)
        self._bus.publish("account.unarchived", {"id": account_id})
        self._log.info("account.unarchived", account=account_id)
        return updated

    def deletion_preview(self, account_id: str) -> dict:
        counts = self._accounts.deletion_counts(account_id)
        blockers: list[str] = []
        if counts.get("sending"):
            blockers.append("job_in_flight")
        if counts.get("jobs"):
            blockers.append("account_in_use")
        if counts.get("sent"):
            blockers.append("history_requires_force_history")
        return {"account_id": account_id, "counts": counts, "blockers": blockers}

    def start_attempt(
        self,
        account_id: str,
        client_id: str | None = None,
        transport: str | None = None,
    ) -> ConnectAttempt:
        account = self._accounts.get(account_id)
        kind = self._transport_kind(transport)
        spec = self._clients.spec_for(account.provider, client_id)
        self._vault.ensure_unlocked()
        attempt = self._flow.start(account, spec)
        if kind is not None:
            self._attempt_transports[attempt.id] = kind
        return attempt

    @staticmethod
    def _transport_kind(value: str | None) -> TransportKind | None:
        if not value:
            return None
        try:
            return TransportKind(value)
        except ValueError as error:
            raise InvalidAccount(
                "unknown transport",
                hint="use smtp or gmail_api",
                fields={"transport": value},
            ) from error

    def attempt(self, attempt_id: str) -> ConnectAttempt:
        return self._flow.get(attempt_id)

    def cancel_attempt(self, attempt_id: str) -> ConnectAttempt:
        return self._flow.cancel(attempt_id)

    def connect_password(self, account_id: str, password: str) -> Account:
        account = self._accounts.get(account_id)
        spec = self._registry.get(account.provider)
        if spec.auth_kind is not AuthKind.APP_PASSWORD:
            raise ProviderAuthMismatch(
                "this provider does not use an app password",
                hint="start an oauth attempt instead",
            )
        self._vault.ensure_unlocked()
        self._flow.stop_for_account(account.id)
        self._login(spec, account, password=password)
        key = secret_key(account.id, "app_password")
        self._vault.set_secret(key, password)
        updated = self._accounts.mark_connected(account.id, key, utc_now())
        self._connected(account, updated)
        return updated

    def verify(self, account_id: str, *, refresh: bool = False) -> Account:
        account = self._accounts.get(account_id)
        spec = self._clients.spec_for_account(account)
        if account.credential_key is None:
            raise CredentialMissing(
                "the account has no credential",
                hint="connect the account first",
            )
        self._vault.ensure_unlocked()
        try:
            if spec.auth_kind is AuthKind.OAUTH2:
                self._verify_oauth(account, spec, refresh)
            elif spec.auth_kind is AuthKind.APP_PASSWORD:
                self._verify_password(account)
            else:
                raise ProviderAuthMismatch("this provider has no authentication")
        except ImapAuthFailed as error:
            self._needs_reauth(account, "imap_auth_failed")
            raise AccountNeedsReauth(
                "the mailbox rejected the credential",
                hint="start a new connect attempt",
            ) from error
        updated = self._accounts.mark_verified(account.id, utc_now())
        if account.status is AccountStatus.NEEDS_REAUTH:
            self._connected(account, updated)
        return updated

    def set_watcher(self, account_id: str, enabled: bool) -> Account:
        account = self._accounts.set_watcher_enabled(account_id, enabled)
        self._inbound.account_changed(account.id, enabled)
        self._bus.publish(
            "account.watcher",
            {"id": account.id, "enabled": enabled},
        )
        self._log.info(
            "account.watcher",
            account=account.id,
            enabled=enabled,
        )
        return account

    def set_inbound(self, account_id: str, source: str) -> Account:
        account = self._accounts.get(account_id)
        if source not in {"auto", "imap", "gmail_api"}:
            raise InvalidAccount(
                "the inbound source is not supported",
                fields={"source": source},
            )
        if source == "gmail_api":
            spec = self._clients.spec_for_account(account)
            if spec.auth_kind is not AuthKind.OAUTH2 or not spec.api_configured:
                raise InvalidAccount(
                    "this mailbox cannot read through the gmail api",
                    hint="only an OAuth Gmail provider has gmail api reads",
                    fields={"source": source},
                )
        updated = self._accounts.set_source_override(
            account.id,
            None if source == "auto" else source,
        )
        self._inbound.account_connected(account.id)
        self._bus.publish(
            "account.inbound",
            {"id": account.id, "source": source},
        )
        self._log.info(
            "account.inbound",
            account=account.id,
            source=source,
        )
        return updated

    def sync(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if account.status is not AccountStatus.CONNECTED:
            raise AccountNeedsReauth(
                "the account is not connected",
                hint="connect the account before syncing",
            )
        self._vault.ensure_unlocked()
        self._inbound.sync_now(account.id)
        return account

    def close_flows(self, reason: str) -> None:
        self._flow.close_all(reason)

    def prune_orphans(self) -> int:
        try:
            known = {account.id for account in self._accounts.list()}
            removed = self._vault.prune_account_secrets(known)
        except VaultLocked:
            return 0
        if removed:
            self._log.info("vault.secrets_pruned", count=removed)
        return removed

from __future__ import annotations

import time

from downcroc.core.events import EventBus
from downcroc.core.inbound import InboundService
from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account, AccountStatus, SendPolicy
from downcroc.domain.attempts import ConnectAttempt
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    ImapAuthFailed,
    ImapTlsFailed,
    ImapUnreachable,
    InvalidAccount,
    OAuthFailed,
    OAuthUnavailable,
    ProviderAuthMismatch,
    ProviderNotConfigured,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.secrets import secret_key
from downcroc.domain.validators import validate_account
from downcroc.mail.imap import connection as imap
from downcroc.providers.oauth import client as oauth_client
from downcroc.providers.oauth.flow import OAuthFlow
from downcroc.providers.registry import ProviderRegistry
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings
from downcroc.runtime.ids import new_id
from downcroc.runtime.logging.setup import EventLogger
from downcroc.store.repositories.accounts import AccountRepo
from downcroc.store.repositories.attempts import AttemptRepo


class AccountsService:
    def __init__(
        self,
        accounts: AccountRepo,
        bus: EventBus,
        log: EventLogger,
        policy: SendPolicy,
        registry: ProviderRegistry,
        vault: VaultService,
        tokens: TokenManager,
        attempts: AttemptRepo,
        settings: ConnectSettings,
        inbound: InboundService,
    ) -> None:
        self._accounts = accounts
        self._bus = bus
        self._log = log
        self._policy = policy
        self._registry = registry
        self._vault = vault
        self._tokens = tokens
        self._settings = settings
        self._inbound = inbound
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
            policy=self._policy,
        )
        self._accounts.create(account)
        self._bus.publish("account.added", {"id": account.id})
        self._log.info("account.created", account=account.id, provider=provider)
        return account

    def list(self) -> list[Account]:
        return self._accounts.list()

    def apply_sending_defaults(self, old: SendPolicy, new: SendPolicy) -> int:
        updated = self._accounts.update_policy_matching(old, new)
        self._policy = new
        return updated

    def get(self, account_id: str) -> Account:
        return self._accounts.get(account_id)

    def delete(self, account_id: str) -> None:
        self._flow.stop_for_account(account_id)
        self._inbound.account_removed(account_id)
        self._accounts.delete(account_id)
        try:
            self._vault.delete_account_secrets(account_id)
        except VaultLocked:
            pass
        self._bus.publish("account.removed", {"id": account_id})
        self._log.info("account.deleted", account=account_id)

    def start_attempt(self, account_id: str) -> ConnectAttempt:
        account = self._accounts.get(account_id)
        spec = self._registry.get(account.provider)
        self._vault.ensure_unlocked()
        return self._flow.start(account, spec)

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
        spec = self._registry.get(account.provider)
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

    def _verify_oauth(
        self, account: Account, spec: ProviderSpec, refresh: bool
    ) -> None:
        token = self._access_token(account, force=refresh)
        try:
            self._login(spec, account, access_token=token)
        except ImapAuthFailed:
            if refresh:
                raise
            token = self._access_token(account, force=True)
            self._login(spec, account, access_token=token)

    def _verify_password(self, account: Account) -> None:
        if account.credential_key is None:
            raise CredentialMissing("the account has no credential")
        try:
            secret = self._vault.get_secret(account.credential_key)
        except VaultSecretMissing as error:
            self._needs_reauth(account, "credential_missing")
            raise CredentialMissing(
                "the credential is missing from the vault",
                hint="connect the account again",
            ) from error
        spec = self._registry.get(account.provider)
        self._login(spec, account, password=secret.value)

    def _access_token(self, account: Account, *, force: bool) -> str:
        try:
            return self._tokens.access_token(account, force=force)
        except NeedsReauth as error:
            self._needs_reauth(account, error.reason)
            raise AccountNeedsReauth(
                "the mailbox needs to be reconnected",
                hint="start a new connect attempt",
            ) from error
        except TokenRefreshUnavailable as error:
            raise OAuthUnavailable(
                "the token endpoint could not be reached",
                hint="try again later",
            ) from error
        except TokenRefreshFailed as error:
            raise OAuthFailed(
                "the access token could not be refreshed",
                hint="check the provider client configuration",
            ) from error
        except VaultSecretMissing as error:
            self._needs_reauth(account, "missing_refresh_token")
            raise AccountNeedsReauth(
                "the refresh token is missing from the vault",
                hint="start a new connect attempt",
            ) from error

    def _complete_oauth(
        self,
        attempt: ConnectAttempt,
        spec: ProviderSpec,
        code: str,
        redirect_uri: str,
        verifier: str,
    ) -> None:
        account = self._accounts.get(attempt.account_id)
        if not spec.imap_configured:
            raise ProviderNotConfigured(
                "the provider has no imap host",
                hint="declare imap_host and imap_port in providers.toml",
            )
        tokens = oauth_client.exchange_code(
            spec,
            code,
            redirect_uri,
            verifier,
            self._settings.oauth_timeout_s,
        )
        scope_count = len(tokens.scopes or spec.oauth_scopes)
        self._log.info(
            "oauth.token",
            expires_in=tokens.expires_in,
            scope_count=scope_count,
            account=account.id,
            attempt=attempt.id,
        )
        if tokens.refresh_token is None:
            raise OAuthFailed(
                "the provider did not return a refresh token",
                hint="start the attempt again and grant offline access",
            )
        self._login(spec, account, access_token=tokens.access_token)
        refresh_key = secret_key(account.id, "refresh_token")
        access_key = secret_key(account.id, "access_token")
        self._vault.set_secrets(
            {
                refresh_key: (tokens.refresh_token, None, ()),
                access_key: (
                    tokens.access_token,
                    utc_after(tokens.expires_in),
                    tokens.scopes or spec.oauth_scopes,
                ),
            }
        )
        updated = self._accounts.mark_connected(account.id, refresh_key, utc_now())
        self._connected(account, updated)

    def _login(
        self,
        spec: ProviderSpec,
        account: Account,
        *,
        password: str | None = None,
        access_token: str | None = None,
    ) -> None:
        if not spec.imap_configured:
            raise ProviderNotConfigured(
                "the provider has no imap host",
                hint="declare imap_host and imap_port in providers.toml",
            )
        started = time.monotonic()
        try:
            imap.login(
                spec,
                account.address,
                password=password,
                access_token=access_token,
                timeout_s=self._settings.imap_timeout_s,
            )
        except imap.ImapAuthError as error:
            self._login_log(spec, account, started, "auth_failed")
            raise ImapAuthFailed(
                "the mailbox rejected the credential",
                hint="check the app password or reconnect the account",
            ) from error
        except imap.ImapTlsError as error:
            self._login_log(spec, account, started, "tls_failed")
            raise ImapTlsFailed(
                "the mailbox certificate could not be verified",
                hint="check the server certificate",
            ) from error
        except imap.ImapNetworkError as error:
            self._login_log(spec, account, started, "unreachable")
            raise ImapUnreachable(
                "the mailbox could not be reached",
                hint="check the host, port and network",
            ) from error
        self._login_log(spec, account, started, "ok")

    def _login_log(
        self,
        spec: ProviderSpec,
        account: Account,
        started: float,
        outcome: str,
    ) -> None:
        duration = round((time.monotonic() - started) * 1000)
        if outcome == "ok":
            self._log.info(
                "imap.login",
                host=spec.imap_host,
                duration_ms=duration,
                outcome=outcome,
                account=account.id,
            )
        else:
            self._log.warning(
                "imap.login",
                host=spec.imap_host,
                duration_ms=duration,
                outcome=outcome,
                account=account.id,
            )

    def _needs_reauth(self, account: Account, reason: str) -> None:
        if (
            account.status is AccountStatus.NEEDS_REAUTH
            and account.last_error == reason
        ):
            return
        updated = self._accounts.mark_needs_reauth(account.id, reason)
        self._inbound.account_changed(account.id, False)
        self._bus.publish("account.needs_reauth", {"id": updated.id, "reason": reason})
        self._log.warning("account.needs_reauth", account=updated.id, reason=reason)

    def _connected(self, previous: Account, updated: Account) -> None:
        self._inbound.account_connected(updated.id)
        if previous.status is AccountStatus.CONNECTED:
            return
        self._bus.publish("account.connected", {"id": updated.id})
        self._log.info(
            "account.connected",
            account=updated.id,
            provider=updated.provider,
        )

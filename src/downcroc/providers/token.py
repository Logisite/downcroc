from __future__ import annotations

import threading
import time

from downcroc.domain.accounts import Account
from downcroc.domain.errors import OAuthNotConfigured, VaultSecretMissing
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.secrets import secret_key
from downcroc.ports.secrets import SecretStore
from downcroc.providers.oauth import client as oauth_client
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import parse_utc, utc_after, utc_now
from downcroc.runtime.config.schema import ConnectSettings
from downcroc.runtime.logging.setup import EventLogger

NEEDS_REAUTH = frozenset({"invalid_grant", "missing_refresh_token"})


class NeedsReauth(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TokenRefreshFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TokenRefreshUnavailable(Exception):
    pass


class TokenManager:
    def __init__(
        self,
        vault: SecretStore,
        registry: ProviderRegistry,
        settings: ConnectSettings,
        log: EventLogger,
    ) -> None:
        self._vault = vault
        self._registry = registry
        self._settings = settings
        self._log = log
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def access_token(
        self,
        account: Account,
        *,
        spec: ProviderSpec | None = None,
        force: bool = False,
    ) -> str:
        spec = spec or self._registry.get(account.provider)
        self._require_oauth(spec)
        with self._lock_for(account.id):
            if not force:
                cached = self._cached(account)
                if cached is not None:
                    return cached
            refresh_key = secret_key(account.id, "refresh_token")
            try:
                refresh = self._vault.get_secret(refresh_key)
            except VaultSecretMissing as error:
                self._log.warning(
                    "oauth.failed", code="missing_refresh_token", account=account.id
                )
                raise NeedsReauth("missing_refresh_token") from error
            started = time.monotonic()
            try:
                tokens = oauth_client.refresh(
                    spec, refresh.value, self._settings.oauth_timeout_s
                )
            except oauth_client.OAuthError as error:
                self._log.warning("oauth.failed", code=error.code, account=account.id)
                if error.code in NEEDS_REAUTH:
                    raise NeedsReauth(error.code) from error
                if error.code == "provider_unavailable":
                    raise TokenRefreshUnavailable from error
                raise TokenRefreshFailed(error.code) from error
            except oauth_client.OAuthUnavailableError as error:
                self._log.warning(
                    "oauth.failed", code="provider_unavailable", account=account.id
                )
                raise TokenRefreshUnavailable from error
            self._store(account, spec, tokens, refresh.value)
            duration = round((time.monotonic() - started) * 1000)
            self._log.info(
                "token.refreshed",
                account=account.id,
                duration_ms=duration,
                expires_in=tokens.expires_in,
                refresh_rotated=tokens.refresh_token is not None,
            )
            return tokens.access_token

    def _cached(self, account: Account) -> str | None:
        try:
            secret = self._vault.get_secret(secret_key(account.id, "access_token"))
        except VaultSecretMissing:
            return None
        if secret.expires_at is None:
            return None
        try:
            expires = parse_utc(secret.expires_at)
        except ValueError:
            return None
        remaining = (expires - parse_utc(utc_now())).total_seconds()
        if remaining > self._settings.token_refresh_margin_s:
            return secret.value
        return None

    def _store(
        self,
        account: Account,
        spec: ProviderSpec,
        tokens: oauth_client.TokenSet,
        refresh_token: str,
    ) -> None:
        records = {
            secret_key(account.id, "access_token"): (
                tokens.access_token,
                utc_after(tokens.expires_in),
                tokens.scopes or spec.oauth_scopes,
            )
        }
        if tokens.refresh_token:
            records[secret_key(account.id, "refresh_token")] = (
                tokens.refresh_token,
                None,
                (),
            )
        else:
            records[secret_key(account.id, "refresh_token")] = (
                refresh_token,
                None,
                (),
            )
        self._vault.set_secrets(records)

    def _require_oauth(self, spec: ProviderSpec) -> None:
        if spec.auth_kind is not AuthKind.OAUTH2:
            raise TokenRefreshFailed("not_oauth")
        if not spec.oauth_configured:
            raise OAuthNotConfigured(
                "the provider has no oauth client id",
                hint="run downcroc provider credentials set gmail --client PATH",
            )

    def _lock_for(self, account_id: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(account_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[account_id] = lock
            return lock

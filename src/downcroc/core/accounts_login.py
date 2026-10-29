from __future__ import annotations

import time

from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.attempts import ConnectAttempt
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    ImapAuthFailed,
    ImapTlsFailed,
    ImapUnreachable,
    OAuthFailed,
    OAuthUnavailable,
    ProviderNotConfigured,
    VaultSecretMissing,
)
from downcroc.domain.providers import ProviderSpec
from downcroc.domain.secrets import secret_key
from downcroc.mail.imap import connection as imap
from downcroc.providers.oauth import client as oauth_client
from downcroc.providers.token import (
    NeedsReauth,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.runtime.clock import utc_after, utc_now


class AccountLoginMixin:
    """IMAP login, OAuth token exchange, and account health transitions."""

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
        spec = self._clients.spec_for_account(account)
        try:
            return self._tokens.access_token(account, spec=spec, force=force)
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
        fields = {
            "host": spec.imap_host,
            "duration_ms": duration,
            "outcome": outcome,
            "account": account.id,
        }
        if outcome == "ok":
            self._log.info("imap.login", **fields)
        else:
            self._log.warning("imap.login", **fields)

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

from __future__ import annotations

from downcroc.core.vault_service import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    CredentialMissing,
    OAuthFailed,
    SmtpUnavailable,
    VaultSecretMissing,
)
from downcroc.domain.providers import AuthKind, ProviderSpec
from downcroc.domain.secrets import secret_key
from downcroc.mail.smtp import sender
from downcroc.providers.token import (
    NeedsReauth,
    TokenManager,
    TokenRefreshFailed,
    TokenRefreshUnavailable,
)
from downcroc.store.repositories.accounts import AccountRepo


class CredentialResolver:
    def __init__(
        self,
        accounts: AccountRepo,
        vault: VaultService,
        tokens: TokenManager,
    ) -> None:
        self._accounts = accounts
        self._vault = vault
        self._tokens = tokens

    def ensure_unlocked(self) -> None:
        self._vault.ensure_unlocked()

    def resolve(self, account: Account, spec: ProviderSpec) -> sender.SmtpCredentials:
        if spec.auth_kind is AuthKind.OAUTH2:
            return self._oauth(account)
        return self._app_password(account)

    def _oauth(self, account: Account) -> sender.SmtpCredentials:
        try:
            token = self._tokens.access_token(account)
        except NeedsReauth as error:
            self._accounts.mark_needs_reauth(account.id, error.reason)
            raise AccountNeedsReauth(
                "the mailbox needs to be reconnected",
                hint="start a new connect attempt",
            ) from error
        except TokenRefreshUnavailable as error:
            raise SmtpUnavailable(
                "the token endpoint could not be reached",
                hint="try again later",
            ) from error
        except TokenRefreshFailed as error:
            raise OAuthFailed(
                "the access token could not be refreshed",
                hint="check the provider client configuration",
            ) from error
        except VaultSecretMissing as error:
            self._accounts.mark_needs_reauth(account.id, "missing_refresh_token")
            raise AccountNeedsReauth(
                "the refresh token is missing from the vault",
                hint="start a new connect attempt",
            ) from error
        return sender.SmtpCredentials(
            address=account.address,
            auth_kind=AuthKind.OAUTH2,
            access_token=token,
        )

    def _app_password(self, account: Account) -> sender.SmtpCredentials:
        key = account.credential_key or secret_key(account.id, "app_password")
        try:
            secret = self._vault.get_secret(key)
        except VaultSecretMissing as error:
            self._accounts.mark_needs_reauth(account.id, "credential_missing")
            raise CredentialMissing(
                "the credential is missing from the vault",
                hint="connect the account again",
            ) from error
        return sender.SmtpCredentials(
            address=account.address,
            auth_kind=AuthKind.APP_PASSWORD,
            password=secret.value,
        )

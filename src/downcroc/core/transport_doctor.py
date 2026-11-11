from __future__ import annotations

from downcroc.core.credentials import CredentialResolver
from downcroc.core.oauth_clients import OAuthClientService
from downcroc.core.transports import validation
from downcroc.core.vault import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import (
    AccountNeedsReauth,
    OAuthClientInvalid,
    OAuthClientNotFound,
    OAuthFailed,
    VaultLocked,
    VaultSecretMissing,
)
from downcroc.domain.secrets import secret_key
from downcroc.domain.transports import AccountTransport, TransportKind
from downcroc.mail.gmail import api as gmail_api
from downcroc.providers.registry import ProviderRegistry
from downcroc.runtime.clock import parse_utc, utc_now
from downcroc.runtime.config.schema import Settings


class TransportChecks:
    """Read-only binding, client, token, API, scope, and clock checks."""

    def __init__(
        self,
        settings: Settings,
        clients: OAuthClientService,
        vault: VaultService,
        registry: ProviderRegistry,
        credentials: CredentialResolver,
    ) -> None:
        self._settings = settings
        self._clients = clients
        self._vault = vault
        self._registry = registry
        self._credentials = credentials

    def checks(
        self,
        account: Account,
        binding: AccountTransport,
    ) -> list[dict[str, object]]:
        spec = self._registry.get(account.provider)
        vault_ok = self._vault_ok(account)
        checks = [
            self._check(
                account,
                binding,
                "vault",
                vault_ok,
                (
                    None
                    if vault_ok
                    else ("vault_locked" if self._locked() else "credential_missing")
                ),
            )
        ]
        if binding.kind is TransportKind.GMAIL_API:
            checks.extend(self._api_checks(account, binding, spec))
        elif spec.auth_kind.value == "oauth2":
            checks.append(self._token_check(account, binding, spec))
        if spec.auth_kind.value == "oauth2":
            skew = self._clock_check(account, binding)
            if skew is not None:
                checks.append(skew)
        return checks

    def _api_checks(self, account, binding, spec) -> list[dict[str, object]]:
        client_id = binding.oauth_client_id or self._clients.account_client(account)
        if client_id is None and not spec.oauth_configured:
            return [
                self._check(
                    account,
                    binding,
                    "oauth_client",
                    False,
                    "missing_oauth_client",
                )
            ]
        if client_id is not None:
            try:
                self._clients.payload(self._clients.get(client_id))
            except (
                OAuthClientInvalid,
                OAuthClientNotFound,
                VaultSecretMissing,
                VaultLocked,
            ):
                return [
                    self._check(
                        account,
                        binding,
                        "oauth_client",
                        False,
                        "oauth_client_invalid",
                    )
                ]
        token = self._token_check(account, binding, spec)
        if not token["ok"]:
            return [token]
        project = self._project_id(account, client_id)
        try:
            access_token = self._credentials.access_token(
                account,
                spec,
                client_id=client_id,
            )
            profile = gmail_api.profile(
                spec,
                access_token,
                timeout_s=self._settings.outbound.api_timeout_s,
                project_id=project,
            )
        except AccountNeedsReauth:
            return [
                self._check(account, binding, "token", False, "account_needs_reauth")
            ]
        except OAuthFailed:
            return [self._check(account, binding, "token", False, "oauth_failed")]
        except gmail_api.GmailApiFailure as error:
            return [
                self._check(
                    account,
                    binding,
                    "api",
                    False,
                    error.code,
                    detail=validation.api_message(error, project),
                )
            ]
        checks = [
            self._check(
                account,
                binding,
                "api",
                True,
                None,
                detail=f"profile answered for {profile.address}",
            )
        ]
        scope = self._scope_check(account, spec)
        if scope is not None:
            checks.append(scope)
        return checks

    def _token_check(self, account, binding, spec) -> dict[str, object]:
        try:
            self._credentials.access_token(
                account,
                spec,
                client_id=binding.oauth_client_id,
            )
        except AccountNeedsReauth:
            return self._check(account, binding, "token", False, "account_needs_reauth")
        except OAuthFailed:
            return self._check(account, binding, "token", False, "oauth_failed")
        except VaultLocked:
            return self._check(account, binding, "token", False, "vault_locked")
        except VaultSecretMissing:
            return self._check(account, binding, "token", False, "credential_missing")
        return self._check(account, binding, "token", True, None)

    def _scope_check(self, account, spec) -> dict[str, object] | None:
        wanted = spec.api_scopes or spec.oauth_scopes
        if not wanted:
            return None
        try:
            secret = self._vault.get_secret(secret_key(account.id, "access_token"))
        except VaultSecretMissing, VaultLocked:
            return None
        if not secret.scopes or set(wanted) & set(secret.scopes):
            return None
        return {
            "account_id": account.id,
            "binding_id": None,
            "kind": "gmail_api",
            "check": "scope",
            "ok": False,
            "code": "oauth_scope_missing",
            "detail": "the access token lacks the gmail scope",
        }

    def _clock_check(self, account, binding) -> dict[str, object] | None:
        try:
            secret = self._vault.get_secret(secret_key(account.id, "access_token"))
        except VaultSecretMissing, VaultLocked:
            return None
        if secret.expires_at is None:
            return None
        try:
            remaining = (
                parse_utc(secret.expires_at) - parse_utc(utc_now())
            ).total_seconds()
        except ValueError:
            return self._check(account, binding, "clock", False, "token_expiry_invalid")
        if remaining > 86_400:
            return self._check(
                account,
                binding,
                "clock",
                False,
                "clock_skew",
                detail=f"token expiry is {int(remaining)}s ahead",
            )
        return self._check(account, binding, "clock", True, None)

    def _vault_ok(self, account: Account) -> bool:
        if self._locked():
            return False
        if account.credential_key is None:
            return False
        try:
            return self._vault.has_secret(account.credential_key)
        except VaultLocked:
            return False

    def _locked(self) -> bool:
        try:
            self._vault.ensure_unlocked()
        except VaultLocked:
            return True
        return False

    def _project_id(self, account: Account, client_id: str | None) -> str | None:
        resolved = client_id or self._clients.account_client(account)
        if resolved is None:
            return None
        try:
            return self._clients.get(resolved).project_id
        except Exception:  # noqa: BLE001 - a missing client has no project
            return None

    @staticmethod
    def _check(
        account: Account,
        binding: AccountTransport,
        check: str,
        ok: bool,
        code: str | None,
        *,
        detail: str | None = None,
    ) -> dict[str, object]:
        return {
            "account_id": account.id,
            "binding_id": binding.id,
            "kind": binding.kind.value,
            "check": check,
            "ok": ok,
            "code": code,
            "detail": detail,
        }

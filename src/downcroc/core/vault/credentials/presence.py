from __future__ import annotations

from downcroc.core.vault.service import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.errors import VaultLocked


class CredentialPresence:
    """Report credential presence from the live vault, never from a stored flag."""

    def __init__(self, vault: VaultService) -> None:
        self._vault = vault

    def present(self, account: Account) -> bool:
        key = account.credential_key
        if key is None:
            return False
        try:
            return self._vault.has_secret(key)
        except VaultLocked:
            return False

    def missing(self, account: Account) -> bool:
        return account.credential_key is not None and not self.present(account)

    @staticmethod
    def kind(account: Account) -> str:
        _, separator, kind = (account.credential_key or "").partition(":")
        return kind if separator else "unknown"

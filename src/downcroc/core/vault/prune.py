from __future__ import annotations

from collections.abc import Iterable

from downcroc.core.vault.credentials.presence import CredentialPresence
from downcroc.core.vault.ports import CredentialDirectory
from downcroc.core.vault.service import VaultService
from downcroc.domain.accounts import Account
from downcroc.domain.secrets import KINDS
from downcroc.runtime.logging.setup import EventLogger


class VaultMaintenance:
    """Prune orphaned account secrets and verify present credentials at unlock."""

    def __init__(
        self,
        vault: VaultService,
        accounts: CredentialDirectory,
        presence: CredentialPresence,
        log: EventLogger,
    ) -> None:
        self._vault = vault
        self._accounts = accounts
        self._presence = presence
        self._log = log

    def on_unlock(self) -> None:
        accounts = self._accounts.credential_accounts()
        self.prune_orphans(accounts)
        self.check_credentials(accounts)

    def prune_orphans(self, accounts: Iterable[Account] | None = None) -> int:
        known = {
            account.id
            for account in (
                accounts
                if accounts is not None
                else self._accounts.credential_accounts()
            )
        }
        keys = self._vault.keys()
        stale = {
            key for key in keys if _is_account_secret(key) and _owner(key) not in known
        }
        if not stale:
            return 0
        removed = self._vault.delete_secrets(stale)
        if not removed:
            return 0
        self._log.info(
            "vault.secrets_pruned",
            accounts=sorted({_owner(key) for key in stale}),
            kinds=sorted({_kind(key) for key in stale}),
            count=removed,
        )
        return removed

    def check_credentials(self, accounts: Iterable[Account] | None = None) -> None:
        for account in (
            accounts if accounts is not None else self._accounts.credential_accounts()
        ):
            if account.credential_key is None:
                continue
            if self._presence.present(account):
                continue
            kind = CredentialPresence.kind(account)
            self._accounts.mark_credential_missing(account.id, kind)
            self._log.warning(
                "account.credential_missing",
                account=account.id,
                kind=kind,
                action="needs_reauth",
            )


def _is_account_secret(key: str) -> bool:
    _, separator, kind = key.partition(":")
    return bool(separator) and kind in KINDS


def _owner(key: str) -> str:
    return key.partition(":")[0]


def _kind(key: str) -> str:
    return key.partition(":")[2]

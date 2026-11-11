from __future__ import annotations

from typing import Protocol

from downcroc.domain.accounts import Account


class CredentialDirectory(Protocol):
    """The narrow account view the vault slice needs at unlock."""

    def credential_accounts(self) -> list[Account]: ...

    def mark_credential_missing(self, account_id: str, kind: str) -> None: ...

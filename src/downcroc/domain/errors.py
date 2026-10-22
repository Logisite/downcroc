from __future__ import annotations


class DomainError(Exception):
    code = "domain_error"
    status = 400

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.fields = fields


class AccountNotFound(DomainError):
    code = "account_not_found"
    status = 404


class AccountExists(DomainError):
    code = "account_exists"
    status = 409


class AccountInUse(DomainError):
    code = "account_in_use"
    status = 409


class InvalidAccount(DomainError):
    code = "invalid_account"
    status = 422


class VaultLocked(DomainError):
    code = "vault_locked"
    status = 423


class VaultBadPassword(DomainError):
    code = "vault_bad_password"
    status = 401


class VaultThrottled(DomainError):
    code = "vault_throttled"
    status = 429


class VaultCorrupt(DomainError):
    code = "vault_corrupt"
    status = 409


class VaultAlreadyUnlocked(DomainError):
    code = "vault_already_unlocked"
    status = 409


class VaultWriteFailed(DomainError):
    code = "vault_write_failed"
    status = 500


class VaultUnavailable(DomainError):
    code = "vault_unavailable"
    status = 500


class VaultSecretMissing(DomainError):
    code = "vault_secret_missing"
    status = 404

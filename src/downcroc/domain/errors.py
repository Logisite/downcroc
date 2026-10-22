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

from __future__ import annotations

from pathlib import Path


class DomainError(Exception):
    code = "domain_error"
    status = 400

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        fields: dict[str, str] | None = None,
        details: list[dict[str, object]] | None = None,
        extra: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.fields = fields
        self.details = details
        self.extra = extra


class ProviderConfigError(Exception):
    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.field = field

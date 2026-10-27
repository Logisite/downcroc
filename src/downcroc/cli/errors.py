from __future__ import annotations

import json
import sys
from typing import Any


class CliError(RuntimeError):
    """One rendered error for every command and for argparse."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        fields: dict[str, Any] | None = None,
        details: list[dict[str, Any]] | dict[str, Any] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint
        self.fields = dict(fields or {})
        self.details = details or []
        self.exit_code = exit_code

    @property
    def label(self) -> str:
        if self.code:
            return f"{self.code}: {self.message}"
        return self.message

    def as_json(self) -> dict[str, Any]:
        return {
            "error": self.code or "error",
            "message": self.message,
            "exit_code": self.exit_code,
            "hint": self.hint,
            "fields": self.fields,
            "details": self.details,
        }


class UsageError(CliError):
    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message, code="usage", hint=hint, exit_code=2)


class Cancelled(CliError):
    def __init__(self, message: str = "cancelled") -> None:
        super().__init__(message, code="cancelled")


def no_terminal(flag: str = "--password-stdin") -> CliError:
    return CliError(
        "no terminal for a password prompt",
        code="no_terminal",
        hint=f"pass {flag} or --password-file PATH",
    )


def render(error: CliError, *, json_mode: bool = False, stream=None) -> None:
    out = stream or sys.stderr
    if json_mode:
        print(json.dumps(error.as_json(), ensure_ascii=False), file=out)
        return
    print(f"error: {error.label}", file=out)
    if error.hint:
        print(f"  hint: {error.hint}", file=out)
    for field, message in error.fields.items():
        print(f"  field: {field}: {message}", file=out)
    for detail in _details(error.details):
        rendered = "  ".join(f"{key}={value}" for key, value in detail.items())
        print(f"  detail: {rendered}", file=out)


def _details(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]

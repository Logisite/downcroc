from __future__ import annotations

from datetime import datetime

from downcroc.core.inputs.report import Issues

MAX_SUBJECT = 998
MAX_KEY = 128
MAX_STEP_DAYS = 365
IGNORED_HEADERS = frozenset(
    {
        "from",
        "date",
        "message-id",
        "message_id",
        "in-reply-to",
        "in_reply_to",
        "references",
        "bcc",
        "cc",
        "content-id",
        "content_id",
        "mime-version",
        "headers",
        "account",
        "account_id",
    }
)


def mapping(raw: object, where: str, issues: Issues) -> dict[str, object]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        issues.add("invalid_field", f"{where} must be an object", where)
        return {}
    return {str(key): value for key, value in raw.items()}


def check_keys(
    raw: dict[str, object], allowed: set[str], where: str, issues: Issues
) -> None:
    for key in raw:
        if key in allowed or key.startswith("x-"):
            continue
        issues.add("unknown_field", f"unknown field {key}", f"{where}.{key}")


def require_text(raw: object, where: str, issues: Issues, *, limit: int) -> str:
    if not isinstance(raw, str):
        if raw is not None:
            issues.add("invalid_field", f"{where} must be a string", where)
        else:
            issues.add("missing_field", f"{where} is required", where)
        return ""
    if len(raw) > limit:
        issues.add("invalid_field", f"{where} is longer than {limit} characters", where)
        return raw[:limit]
    return raw


def optional_text(
    raw: object, where: str, issues: Issues, *, limit: int = 1_000_000
) -> str | None:
    if raw is None:
        return None
    return require_text(raw, where, issues, limit=limit)


def text_list(raw: object, where: str, issues: Issues) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        issues.add("invalid_field", f"{where} must be an array of strings", where)
        return ()
    return tuple(raw)


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True

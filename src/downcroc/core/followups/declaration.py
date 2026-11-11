from __future__ import annotations

import json
import re
from dataclasses import dataclass

from downcroc.core.inputs.campaign_message import parse_overrides
from downcroc.core.inputs.field_input import (
    MAX_KEY,
    MAX_STEP_DAYS,
    MAX_SUBJECT,
    is_int,
    optional_text,
)
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import FOLLOWUP_WHEN, FollowUpOverride
from downcroc.domain.errors import FollowUpInvalid, InputUnreadable
from downcroc.domain.followups import DeclarationKind

SHARED_KEYS = {
    "after_days",
    "when",
    "subject",
    "text",
    "html",
    "require_approval",
    "overrides",
}
_STEP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class SharedDeclaration:
    after_days: int
    when: str
    subject: str | None
    text: str | None
    html: str | None
    require_approval: bool
    overrides: dict[str, FollowUpOverride]


def detect_kind(raw: bytes) -> DeclarationKind:
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputUnreadable("a follow-up declaration must be valid JSON") from error
    if isinstance(document, list):
        return DeclarationKind.PAYLOAD
    if not isinstance(document, dict):
        raise FollowUpInvalid("a follow-up declaration must be an object")
    if isinstance(document.get("messages"), list):
        return DeclarationKind.PAYLOAD
    return DeclarationKind.SHARED


def check_step_key(step_key: str) -> str:
    value = step_key.strip()
    if not value or len(value) > MAX_KEY or not _STEP.fullmatch(value):
        raise FollowUpInvalid(
            "the step key is not valid",
            hint="use letters, digits, dots, dashes, or underscores",
            fields={"step": value},
        )
    return value


def parse_shared(
    raw: bytes, *, step_key: str, limits: IntakeLimits
) -> SharedDeclaration:
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputUnreadable("a follow-up declaration must be valid JSON") from error
    if not isinstance(document, dict):
        raise FollowUpInvalid("a shared declaration must be an object")
    issues = Issues()
    for key in document:
        if key not in SHARED_KEYS and not key.startswith("x-"):
            issues.add("unknown_field", f"unknown field {key}", key)
    after_days = document.get("after_days")
    if not is_int(after_days) or not 1 <= after_days <= MAX_STEP_DAYS:
        issues.add(
            "invalid_field",
            f"after_days must be between 1 and {MAX_STEP_DAYS}",
            "after_days",
        )
        after_days = 1
    when = document.get("when", "no_reply")
    if when not in FOLLOWUP_WHEN:
        issues.add(
            "invalid_field",
            f"when must be one of {sorted(FOLLOWUP_WHEN)}",
            "when",
        )
        when = "no_reply"
    subject = optional_text(
        document.get("subject"), "subject", issues, limit=MAX_SUBJECT
    )
    text = optional_text(
        document.get("text"), "text", issues, limit=limits.max_body_bytes
    )
    html = optional_text(
        document.get("html"), "html", issues, limit=limits.max_body_bytes
    )
    if not text and not html:
        issues.add(
            "missing_content",
            "a shared declaration needs text or html",
            "text",
        )
    require_approval = document.get("require_approval", False)
    if not isinstance(require_approval, bool):
        issues.add(
            "invalid_field",
            "require_approval must be a boolean",
            "require_approval",
        )
        require_approval = False
    overrides = parse_overrides(
        document.get("overrides", {}), "declaration", issues, step_key
    )
    issues.raise_if_any()
    return SharedDeclaration(
        after_days=after_days,
        when=str(when),
        subject=subject,
        text=text,
        html=html,
        require_approval=require_approval,
        overrides=overrides,
    )

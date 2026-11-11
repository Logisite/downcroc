from __future__ import annotations

from pathlib import Path

from downcroc.core.inputs.field_input import (
    IGNORED_HEADERS,
    MAX_KEY,
    MAX_SUBJECT,
    check_keys,
    mapping,
    optional_text,
    require_text,
)
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import FollowUpOverride, IgnoredField, Message, Recipient
from downcroc.domain.validators import ADDRESS


def parse_message(
    raw: object,
    index: int,
    source_dir: Path,
    limits: IntakeLimits,
    issues: Issues,
    ignored: list[IgnoredField],
    *,
    allow_empty_subject: bool = False,
) -> Message:
    where = f"messages[{index}]"
    body = mapping(raw, where, issues)
    allowed = {
        "key",
        "to",
        "subject",
        "text",
        "html",
        "reply_to",
        "attachments",
        "followups",
    }
    for field_name in body:
        folded = field_name.casefold()
        if folded in IGNORED_HEADERS:
            ignored.append(
                IgnoredField(
                    key=str(body.get("key", f"m{index + 1}")), field=field_name
                )
            )
            continue
        if field_name not in allowed and not field_name.startswith("x-"):
            issues.add(
                "unknown_field", f"unknown field {field_name}", f"{where}.{field_name}"
            )
    key = require_text(
        body.get("key", f"m{index + 1}"), f"{where}.key", issues, limit=MAX_KEY
    )
    to = mapping(body.get("to"), f"{where}.to", issues)
    check_keys(to, {"email", "name"}, f"{where}.to", issues)
    email = require_text(to.get("email"), f"{where}.to.email", issues, limit=320)
    if email and not ADDRESS.fullmatch(email):
        issues.add(
            "invalid_address",
            f"{email} is not an email address",
            f"{where}.to.email",
            key=key,
        )
    name = optional_text(to.get("name"), f"{where}.to.name", issues, limit=200)
    subject_raw = body.get("subject")
    if isinstance(subject_raw, str):
        subject = subject_raw
        if not subject.strip():
            if not allow_empty_subject:
                issues.add(
                    "empty_subject",
                    "subject is empty",
                    f"{where}.subject",
                    key=key,
                )
        elif len(subject) > MAX_SUBJECT:
            issues.add(
                "invalid_field",
                f"subject is longer than {MAX_SUBJECT} characters",
                f"{where}.subject",
                key=key,
            )
            subject = subject[:MAX_SUBJECT]
    else:
        subject = ""
        if not allow_empty_subject:
            issues.add(
                "missing_subject", "subject is required", f"{where}.subject", key=key
            )
    text = optional_text(
        body.get("text"), f"{where}.text", issues, limit=limits.max_body_bytes
    )
    html = optional_text(
        body.get("html"), f"{where}.html", issues, limit=limits.max_body_bytes
    )
    if not text and not html:
        issues.add(
            "missing_content",
            "a message needs text or html",
            f"{where}.text",
            key=key,
        )
    reply_to = optional_text(
        body.get("reply_to"), f"{where}.reply_to", issues, limit=320
    )
    if reply_to and not ADDRESS.fullmatch(reply_to):
        issues.add(
            "invalid_address",
            f"{reply_to} is not an email address",
            f"{where}.reply_to",
            key=key,
        )
    attachments = attachment_refs(
        body.get("attachments", []), where, source_dir, limits, issues, key
    )
    overrides = parse_overrides(body.get("followups", {}), where, issues, key)
    return Message(
        key=key or f"m{index + 1}",
        recipient=Recipient(email=email or "", name=name),
        subject=subject,
        text=text or "",
        html=html,
        reply_to=reply_to,
        attachments=attachments,
        overrides=overrides,
        source_index=index,
    )


def parse_overrides(
    raw: object, where: str, issues: Issues, key: str
) -> dict[str, FollowUpOverride]:
    if raw is None:
        return {}
    fields = mapping(raw, f"{where}.followups", issues)
    overrides: dict[str, FollowUpOverride] = {}
    for step_key, value in fields.items():
        field = f"{where}.followups.{step_key}"
        check_keys(value, {"subject", "text", "html", "skip"}, field, issues)
        body = mapping(value, field, issues)
        skip = body.get("skip", False)
        if not isinstance(skip, bool):
            issues.add(
                "invalid_field", "skip must be a boolean", f"{field}.skip", key=key
            )
        overrides[step_key] = FollowUpOverride(
            subject=optional_text(
                body.get("subject"), f"{field}.subject", issues, limit=MAX_SUBJECT
            ),
            text=optional_text(body.get("text"), f"{field}.text", issues),
            html=optional_text(body.get("html"), f"{field}.html", issues),
            skip=skip is True,
        )
    return overrides


def attachment_refs(
    raw: object,
    where: str,
    source_dir: Path,
    limits: IntakeLimits,
    issues: Issues,
    key: str,
) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        issues.add(
            "invalid_field",
            "attachments must be an array of filenames",
            f"{where}.attachments",
            key=key,
        )
        return ()
    resolved: list[str] = []
    root = source_dir.resolve()
    for item in raw:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            issues.add(
                "attachment_path",
                f"attachment {item} must stay inside {source_dir}",
                f"{where}.attachments",
                key=key,
            )
            continue
        target = (source_dir / relative).resolve()
        if root not in target.parents and target != root:
            issues.add(
                "attachment_path",
                f"attachment {item} escapes {source_dir}",
                f"{where}.attachments",
                key=key,
            )
            continue
        if not target.is_file():
            issues.add(
                "attachment_missing",
                f"attachment {item} does not exist",
                f"{where}.attachments",
                key=key,
            )
            continue
        if target.stat().st_size > limits.max_attachment_bytes:
            issues.add(
                "attachment_too_large",
                f"attachment {item} is above {limits.max_attachment_bytes} bytes",
                f"{where}.attachments",
                key=key,
            )
            continue
        resolved.append(item)
    return tuple(resolved)


def check_duplicates(messages: list[Message], issues: Issues) -> None:
    seen: dict[str, Message] = {}
    for message in messages:
        address = message.recipient.email.strip().lower()
        if not address:
            continue
        previous = seen.get(address)
        if previous is None:
            seen[address] = message
            continue
        issues.add(
            "duplicate_address",
            f"{address} appears in both {previous.key} and {message.key}",
            f"messages[{message.source_index}].to.email",
            key=message.key,
        )

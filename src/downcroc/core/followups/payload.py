from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from downcroc.core.inputs.campaign_input import parse_campaign
from downcroc.core.inputs.field_input import MAX_KEY, MAX_STEP_DAYS, is_int
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import FOLLOWUP_WHEN, Campaign, IgnoredField, Message
from downcroc.domain.errors import FollowUpInvalid, InputUnreadable

TOP_LEVEL = {
    "schema",
    "campaign",
    "messages",
    "producer",
    "options",
    "followups",
    "followup",
}
SCHEDULE_KEYS = {"after_days", "when", "require_approval"}


@dataclass(frozen=True)
class PayloadSchedule:
    after_days: int
    when: str
    require_approval: bool


@dataclass(frozen=True)
class PayloadDocument:
    campaign: Campaign
    schedule: PayloadSchedule | None
    ignored: tuple[IgnoredField, ...]
    raw: bytes

    def message_for(self, source_key: str | None, recipient: str) -> Message | None:
        by_key = {message.key: message for message in self.campaign.messages}
        by_email = {
            message.recipient.email.lower(): message
            for message in self.campaign.messages
        }
        if source_key is not None:
            found = by_key.get(source_key)
            if found is not None and found.recipient.email.lower() == recipient.lower():
                return found
        return by_email.get(recipient.lower())

    def gaps(self, parents: list[tuple[str | None, str]]) -> list[str]:
        return [email for key, email in parents if self.message_for(key, email) is None]

    def extras(self, parents: list[tuple[str | None, str]]) -> list[str]:
        wanted = {email.lower() for _, email in parents}
        return [
            message.recipient.email
            for message in self.campaign.messages
            if message.recipient.email.lower() not in wanted
        ]


def detect_payload(document: object) -> bool:
    return isinstance(document, dict) and isinstance(document.get("messages"), list)


def parse_payload_document(
    raw: bytes,
    *,
    name: str,
    source_dir: Path,
    limits: IntakeLimits,
    require_schedule: bool,
    declaration: bool = True,
) -> PayloadDocument:
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputUnreadable("a follow-up declaration must be valid JSON") from error
    if isinstance(document, list):
        document = {"messages": document}
    if not isinstance(document, dict):
        raise FollowUpInvalid("a payload declaration must be an object")
    issues = Issues()
    for key in document:
        if key not in TOP_LEVEL and not key.startswith("x-"):
            issues.add(
                "unknown_field",
                f"unknown field {key}",
                key,
            )
    if declaration and "followups" in document:
        issues.add(
            "unsupported",
            "a payload declaration cannot declare nested follow-ups",
            "followups",
        )
    schedule = _schedule(document.get("followup"), require_schedule, issues)
    body = {
        key: value
        for key, value in document.items()
        if key not in {"followup", "options"}
    }
    campaign = parse_campaign(
        body,
        source_dir=source_dir,
        name=name,
        limits=limits,
        allow_empty_subject=True,
    )
    if declaration:
        _check_payload_messages(campaign, issues)
    issues.raise_if_any()
    return PayloadDocument(
        campaign=campaign,
        schedule=schedule,
        ignored=campaign.ignored,
        raw=raw,
    )


def _schedule(raw: object, required: bool, issues: Issues) -> PayloadSchedule | None:
    if raw is None:
        if required:
            issues.add(
                "missing_field",
                "a scheduled payload needs a followup block",
                "followup",
            )
        return None
    if not isinstance(raw, dict):
        issues.add("invalid_field", "followup must be an object", "followup")
        return None
    for key in raw:
        if key not in SCHEDULE_KEYS and not key.startswith("x-"):
            issues.add(
                "unknown_field",
                f"unknown field {key}",
                f"followup.{key}",
            )
    after_days = raw.get("after_days")
    if not is_int(after_days) or not 1 <= after_days <= MAX_STEP_DAYS:
        issues.add(
            "invalid_field",
            f"after_days must be between 1 and {MAX_STEP_DAYS}",
            "followup.after_days",
        )
        after_days = 1
    when = raw.get("when", "no_reply")
    if when not in FOLLOWUP_WHEN:
        issues.add(
            "invalid_field",
            f"when must be one of {sorted(FOLLOWUP_WHEN)}",
            "followup.when",
        )
        when = "no_reply"
    require_approval = raw.get("require_approval", False)
    if not isinstance(require_approval, bool):
        issues.add(
            "invalid_field",
            "require_approval must be a boolean",
            "followup.require_approval",
        )
        require_approval = False
    return PayloadSchedule(
        after_days=after_days,
        when=str(when),
        require_approval=require_approval,
    )


def _check_payload_messages(campaign: Campaign, issues: Issues) -> None:
    for message in campaign.messages:
        where = f"messages[{message.source_index}]"
        if message.attachments:
            issues.add(
                "unsupported",
                "payload-backed declarations cannot carry attachments",
                f"{where}.attachments",
                key=message.key,
            )
        for field, value in (
            ("subject", message.subject),
            ("text", message.text),
            ("html", message.html or ""),
        ):
            if "{{" in value or "}}" in value:
                issues.add(
                    "unsupported",
                    "template variables are not supported in declarations",
                    f"{where}.{field}",
                    key=message.key,
                )
        if len(message.key) > MAX_KEY:
            issues.add(
                "invalid_field",
                f"message key is longer than {MAX_KEY} characters",
                f"{where}.key",
                key=message.key,
            )


def reply_subject(parent_subject: str) -> str:
    folded = parent_subject.strip().casefold()
    if folded.startswith("re:"):
        return parent_subject
    return f"Re: {parent_subject}"

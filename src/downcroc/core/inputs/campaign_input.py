from __future__ import annotations

from pathlib import Path

from downcroc.core.inputs.campaign_followup import parse_followups
from downcroc.core.inputs.campaign_message import check_duplicates, parse_message
from downcroc.core.inputs.campaign_policy import parse_options, parse_routing
from downcroc.core.inputs.field_input import (
    MAX_KEY,
    check_keys,
    mapping,
    require_text,
)
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import (
    SCHEMA,
    Campaign,
    FollowUpStep,
    IgnoredField,
    Message,
)
from downcroc.domain.errors import BatchInvalid, UnsupportedSchema


def parse_campaign(
    raw: object,
    *,
    source_dir: Path,
    name: str,
    limits: IntakeLimits,
    allow_empty_subject: bool = False,
) -> Campaign:
    issues = Issues()
    if isinstance(raw, list):
        messages_raw = raw
        campaign_raw: dict[str, object] = {}
        producer: dict[str, object] = {}
        followups_raw: list[object] = []
        schema = SCHEMA
    elif isinstance(raw, dict):
        _check_schema_keys(raw, issues)
        schema = _schema(raw)
        campaign_raw = mapping(raw.get("campaign", {}), "campaign", issues)
        producer = mapping(raw.get("producer", {}), "producer", issues)
        messages_raw = _messages_array(raw)
        followups_raw = _followups_array(raw)
    else:
        raise BatchInvalid("source must be a JSON object or array")

    check_keys(campaign_raw, {"key", "name", "routing", "options"}, "campaign", issues)
    campaign_key = require_text(
        campaign_raw.get("key", Path(name).stem), "campaign.key", issues, limit=MAX_KEY
    )
    campaign_name = require_text(
        campaign_raw.get("name", campaign_key), "campaign.name", issues, limit=200
    )
    routing = parse_routing(campaign_raw.get("routing", {}), issues)
    options = parse_options(campaign_raw.get("options", {}), issues)
    followups = parse_followups(followups_raw, limits, issues)
    ignored: list[IgnoredField] = []

    if len(messages_raw) > limits.max_messages:
        raise BatchInvalid(
            f"{len(messages_raw)} messages exceeds the limit of {limits.max_messages}",
            hint="split the campaign or raise intake.max_messages",
        )
    messages = [
        parse_message(
            item,
            index,
            source_dir,
            limits,
            issues,
            ignored,
            allow_empty_subject=allow_empty_subject,
        )
        for index, item in enumerate(messages_raw)
    ]
    if not messages:
        raise BatchInvalid("the campaign has no messages")

    _check_references(messages, followups, issues)
    if not options.allow_duplicates:
        check_duplicates(messages, issues)

    issues.raise_if_any()
    return Campaign(
        schema=schema,
        key=campaign_key,
        name=campaign_name,
        producer=producer,
        routing=routing,
        options=options,
        messages=tuple(messages),
        followups=tuple(followups),
        source_kind="json",
        source_dir=str(source_dir),
        ignored=tuple(ignored),
    )


def _check_schema_keys(raw: dict[str, object], issues: Issues) -> None:
    check_keys(
        raw,
        {"schema", "producer", "campaign", "messages", "followups"},
        "campaign",
        issues,
    )


def _schema(raw: dict[str, object]) -> str:
    schema = raw.get("schema", SCHEMA)
    if not isinstance(schema, str):
        raise BatchInvalid(
            "schema must be a string", fields={"schema": "must be a string"}
        )
    if schema != SCHEMA:
        raise UnsupportedSchema(
            f"schema {schema!r} is not supported",
            hint=f"this daemon understands {SCHEMA}",
        )
    return schema


def _messages_array(raw: dict[str, object]) -> list[object]:
    messages = raw.get("messages")
    if not isinstance(messages, list):
        raise BatchInvalid(
            "messages must be an array",
            fields={"messages": "must be an array"},
        )
    return messages


def _followups_array(raw: dict[str, object]) -> list[object]:
    followups = raw.get("followups", [])
    if not isinstance(followups, list):
        raise BatchInvalid(
            "followups must be an array",
            fields={"followups": "must be an array"},
        )
    return followups


def _check_references(
    messages: list[Message], followups: list[FollowUpStep], issues: Issues
) -> None:
    step_keys = {step.key for step in followups}
    seen_keys: dict[str, int] = {}
    for message in messages:
        previous = seen_keys.get(message.key)
        if previous is not None:
            issues.add(
                "duplicate_key",
                f"message key {message.key} is also used by message {previous + 1}",
                f"messages[{message.source_index}].key",
                key=message.key,
            )
        seen_keys[message.key] = message.source_index
        for step_key in message.overrides:
            if step_key not in step_keys:
                issues.add(
                    "unknown_step",
                    f"message {message.key} overrides unknown step {step_key}",
                    f"messages[{message.source_index}].followups.{step_key}",
                    key=message.key,
                )

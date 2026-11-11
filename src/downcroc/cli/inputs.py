from __future__ import annotations

import json
import logging
from pathlib import Path

from downcroc.core.batches.source import CampaignReader
from downcroc.core.inputs import detector
from downcroc.domain.errors import BatchInvalid, DomainError, InputUnreadable
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


def _log() -> EventLogger:
    logger = logging.getLogger("downcroc.cli.inputs")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
    return EventLogger(logger)


def kind_of(path: Path, settings: Settings) -> str:
    payload = detector.read_source(path, settings.intake.max_file_bytes)
    return detector.detect(payload)


def read(path: Path, template: str | None, settings: Settings, paths: Paths) -> dict:
    reader = CampaignReader(settings, paths, _log())
    return _describe(reader.read(str(path), template))


def _describe(campaign: object) -> dict:
    messages = campaign.messages
    return {
        "ok": True,
        "kind": campaign.source_kind,
        "campaign": {
            "key": campaign.key,
            "name": campaign.name,
            "schema": campaign.schema,
        },
        "messages": len(messages),
        "valid": len(messages),
        "duplicates": campaign.duplicates,
        "ignored": [item.field for item in campaign.ignored],
        "warnings": [],
        "routing": {
            "mode": campaign.routing.mode,
            "account": campaign.routing.account,
            "include": list(campaign.routing.include),
            "exclude": list(campaign.routing.exclude),
        },
        "options": {
            "approval": campaign.options.approval,
            "allow_duplicates": campaign.options.allow_duplicates,
            "suppress_replies": campaign.options.suppress_replies,
            "reply_window_days": campaign.options.reply_window_days,
            "not_before": campaign.options.not_before,
            "stop_on": list(campaign.options.stop_on),
        },
        "followups": [
            {
                "key": step.key,
                "after_days": step.after_days,
                "when": step.when,
                "require_approval": step.require_approval,
            }
            for step in campaign.followups
        ],
        "attachments": sum(len(message.attachments) for message in messages),
    }


def failure(path: Path, error: DomainError) -> dict:
    details = error.details or []
    issues = [
        {
            "code": item.get("code", error.code),
            "message": item.get("message", ""),
            "field": item.get("field", ""),
            "key": item.get("key"),
            "row": item.get("row"),
        }
        for item in details
        if isinstance(item, dict)
    ]
    if not issues:
        issues = [
            {
                "code": error.code,
                "message": getattr(error, "message", str(error)),
                "field": next(iter(getattr(error, "fields", None) or {}), "source"),
                "key": None,
                "row": None,
            }
        ]
    return {
        "ok": False,
        "path": str(path),
        "kind": _kind_hint(path),
        "messages": 0,
        "valid": 0,
        "warnings": [],
        "issues": issues,
        "hint": getattr(error, "hint", None),
    }


def _kind_hint(path: Path) -> str:
    try:
        first = path.read_bytes().lstrip()[:1]
    except OSError:
        return "unknown"
    return "json" if first in {b"{", b"["} else "csv"


def validate(
    path: Path, template: str | None, settings: Settings, paths: Paths
) -> dict:
    try:
        body = read(path, template, settings, paths)
    except (BatchInvalid, InputUnreadable) as error:
        return failure(path, error)
    body["path"] = str(path)
    body["issues"] = []
    return body


EXAMPLES = {
    "json": {
        "campaign.json": {
            "schema": "downcroc.campaign/v1",
            "producer": {"name": "downcroc-example", "version": "1"},
            "campaign": {
                "key": "example",
                "name": "Example campaign",
                "routing": {"mode": "auto"},
                "options": {"approval": "review"},
            },
            "messages": [
                {
                    "key": "m1",
                    "to": {"email": "ana@example.com", "name": "Ana"},
                    "subject": "Hello from downcroc",
                    "text": "Hi Ana,\n\nthis is a plain text message.\n",
                },
                {
                    "key": "m2",
                    "to": {"email": "bo@example.com"},
                    "subject": "Hello from downcroc",
                    "text": "Hi Bo,\n\nthis is a plain text message.\n",
                },
            ],
            "followups": [],
        }
    },
    "followups": {
        "campaign.json": {
            "schema": "downcroc.campaign/v1",
            "campaign": {
                "key": "followup",
                "name": "Campaign with a follow-up",
                "options": {"approval": "review"},
            },
            "messages": [
                {
                    "key": "m1",
                    "to": {"email": "ana@example.com"},
                    "subject": "Hello",
                    "text": "Hi Ana,\n",
                }
            ],
            "followups": [
                {
                    "key": "day3",
                    "after_days": 3,
                    "when": "no_reply",
                    "subject": "Following up",
                    "text": "Hi again,\n",
                }
            ],
        },
        "shared.json": {
            "after_days": 3,
            "when": "no_reply",
            "subject": "",
            "text": "Just following up on my note.",
            "require_approval": True,
            "overrides": {"m1": {"skip": True}},
        },
        "payload.json": {
            "followup": {
                "after_days": 3,
                "when": "no_reply",
                "require_approval": True,
            },
            "messages": [
                {
                    "key": "m1",
                    "to": {"email": "ana@example.com"},
                    "subject": "A different note for Ana",
                    "text": "Hi Ana, one more thought.\n",
                }
            ],
        },
    },
    "csv": {
        "rows.csv": "email,name,company\nana@example.com,Ana,Acme\nbo@example.com,Bo,Globex\n",
    },
    "template": {
        "intro/template.toml": (
            'subject = "Hello {{ name }}"\n'
            'reply_to = "you@example.com"\n'
            "\n"
            "[defaults]\n"
            'name = "there"\n'
        ),
        "intro/body.txt": (
            "Hi {{ name }},\n\n"
            "this is a plain text template. Variables are {{ name }} and {{ company }}.\n"
        ),
        "rows.csv": "email,name,company\nana@example.com,Ana,Acme\n",
    },
}


def write_example(kind: str, directory: Path) -> list[Path]:
    written: list[Path] = []
    for name, content in EXAMPLES[kind].items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            target.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        else:
            target.write_text(content, encoding="utf-8")
        written.append(target)
    return written

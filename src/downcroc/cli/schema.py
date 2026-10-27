from __future__ import annotations

from downcroc.core.inputs.field_input import MAX_KEY

SCHEMA = "downcroc.campaign/v1"

CONTRACT: dict = {
    "schema": SCHEMA,
    "detection": {
        "json": "the first non-space byte is { or [",
        "csv": "anything else; needs --template",
        "encoding": "UTF-8",
    },
    "top_level": ["schema", "producer", "campaign", "messages", "followups"],
    "campaign": {
        "key": f"string, at most {MAX_KEY} characters; defaults to the file stem",
        "name": "string; defaults to the key",
        "routing": {
            "mode": ["auto", "fixed"],
            "account": "account id or address; required when mode is fixed",
            "include": "list of account ids or addresses",
            "exclude": "list of account ids or addresses",
        },
        "options": {
            "approval": ["review", "auto"],
            "suppress_replies": "boolean, default true",
            "reply_window_days": "integer 0-3650, default 60",
            "not_before": "ISO 8601 timestamp",
            "stop_on": ["reply", "bounce"],
            "allow_duplicates": "boolean, default false",
        },
    },
    "producer": "free-form object, stored with the batch",
    "messages": {
        "key": f"string, at most {MAX_KEY} characters; defaults to mN",
        "to": {"email": "required", "name": "optional"},
        "subject": "required, non-empty",
        "text": "plain text body",
        "html": "optional HTML body",
        "reply_to": "optional address",
        "attachments": "list of paths relative to the campaign file",
        "followups": "per-step overrides keyed by step key",
        "ignored": "standard mail headers such as Message-ID are dropped and reported",
    },
    "followups": {
        "key": f"string, at most {MAX_KEY} characters; unique",
        "after_days": "integer 1-365",
        "when": ["no_reply", "always"],
        "subject": "optional; defaults to Re: the original subject",
        "text": "required body",
        "html": "optional HTML body",
        "require_approval": "boolean, default false",
    },
    "csv": {
        "requirement": "a template is required",
        "builtins": ["email", "batch_name", "date"],
        "variables": "any other column name, used as {{ name }}",
    },
    "template": {
        "path": "<config>/templates/<name>/ or a directory path",
        "files": ["template.toml", "body.txt", "body.html", "assets/"],
        "manifest": {
            "subject": "required",
            "reply_to": "optional",
            "attachments": "list of filenames under assets/",
            "defaults": "table of default variable values",
        },
    },
    "approval": {
        "review": "every message is held until approved",
        "auto": "messages are queued as soon as they are due",
        "batch submit --approve none|one|all": "overrides the file for this submission",
    },
    "routing_note": "a per-message account field is rejected; use campaign.routing.account"
    " or submit with --account",
}

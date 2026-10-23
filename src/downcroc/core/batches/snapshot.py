from __future__ import annotations

import json

from downcroc.domain.campaign import Campaign, FollowUpOverride


def campaign_bytes(campaign: Campaign) -> bytes:
    document = {
        "schema": campaign.schema,
        "producer": campaign.producer,
        "source": {"kind": campaign.source_kind, "template": campaign.template},
        "campaign": {
            "key": campaign.key,
            "name": campaign.name,
            "routing": {
                "mode": campaign.routing.mode,
                "account": campaign.routing.account,
                "include": list(campaign.routing.include),
                "exclude": list(campaign.routing.exclude),
            },
            "options": {
                "suppress_replies": campaign.options.suppress_replies,
                "reply_window_days": campaign.options.reply_window_days,
                "not_before": campaign.options.not_before,
                "stop_on": list(campaign.options.stop_on),
                "allow_duplicates": campaign.options.allow_duplicates,
                "approval": campaign.options.approval,
            },
        },
        "messages": [
            {
                "key": message.key,
                "to": {
                    "email": message.recipient.email,
                    "name": message.recipient.name,
                },
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
                "reply_to": message.reply_to,
                "attachments": list(message.attachments),
                "followups": {
                    key: _override_document(value)
                    for key, value in message.overrides.items()
                },
            }
            for message in campaign.messages
        ],
        "followups": [
            {
                "key": step.key,
                "after_days": step.after_days,
                "when": step.when,
                "subject": step.subject,
                "text": step.text,
                "html": step.html,
                "require_approval": step.require_approval,
            }
            for step in campaign.followups
        ],
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _override_document(value: FollowUpOverride) -> dict[str, object]:
    document: dict[str, object] = {}
    if value.skip:
        document["skip"] = True
    if value.subject is not None:
        document["subject"] = value.subject
    if value.text is not None:
        document["text"] = value.text
    if value.html is not None:
        document["html"] = value.html
    return document

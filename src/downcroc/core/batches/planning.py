from __future__ import annotations

import json
from pathlib import Path

from downcroc.core.batches.views import (
    PreviewAttachments,
    PreviewRouting,
)
from downcroc.core.inputs.routing import RoutingPlan
from downcroc.domain.batches import BatchKind, BatchState, NewBatch
from downcroc.domain.campaign import Campaign, Message
from downcroc.domain.errors import BatchInvalid
from downcroc.store.content import StoredContent
from downcroc.store.repositories.replies import DEFAULT_REPLY_WINDOW_DAYS


def select_messages(campaign: Campaign, key: str) -> tuple[Message, ...]:
    chosen = tuple(
        message
        for message in campaign.messages
        if message.key == key or str(message.source_index) == key
    )
    if not chosen:
        raise BatchInvalid(
            f"no message or row matches {key}",
            fields={"key": "not found in the source"},
        )
    return chosen


def reply_window(options_json: str) -> int:
    try:
        options = json.loads(options_json or "{}")
    except json.JSONDecodeError:
        return DEFAULT_REPLY_WINDOW_DAYS
    value = options.get("reply_window_days")
    if isinstance(value, int) and value >= 0:
        return value
    return DEFAULT_REPLY_WINDOW_DAYS


def routing_view(campaign: Campaign, plan: RoutingPlan | None) -> PreviewRouting:
    if plan is None:
        return PreviewRouting(
            mode=campaign.routing.mode,
            account_id=campaign.routing.account,
            counts={},
            unresolved=True,
        )
    counts: dict[str, int] = {}
    for account_id in plan.assignments.values():
        counts[account_id] = counts.get(account_id, 0) + 1
    return PreviewRouting(
        mode=plan.mode,
        account_id=plan.account_id,
        counts=counts,
    )


def attachments(campaign: Campaign) -> PreviewAttachments:
    names = [name for message in campaign.messages for name in message.attachments]
    total = 0
    root = Path(campaign.source_dir) if campaign.source_dir else None
    for name in names:
        candidate = Path(name)
        if not candidate.is_absolute() and root is not None:
            candidate = root / candidate
        try:
            total += candidate.stat().st_size
        except OSError:
            continue
    return PreviewAttachments(count=len(names), bytes=total)


def new_batch(
    campaign: Campaign,
    plan: RoutingPlan,
    batch_id: str,
    approval: str,
    stored: StoredContent,
    chosen: tuple[str, ...],
    started_at: str,
    submit_key: str | None = None,
) -> NewBatch:
    return NewBatch(
        id=batch_id,
        kind=BatchKind.CAMPAIGN,
        parent_batch_id=None,
        name=campaign.name,
        source_ref=stored.path,
        source_hash=stored.hash,
        source_kind=campaign.source_kind,
        schema_version=campaign.schema if campaign.source_kind == "json" else None,
        campaign_key=campaign.key,
        producer_json=json.dumps(campaign.producer, sort_keys=True),
        template_ref=campaign.template,
        account_id=plan.account_id,
        routing_json=plan.as_json(),
        approval=approval,
        options_json=json.dumps(
            {
                "suppress_replies": campaign.options.suppress_replies,
                "reply_window_days": campaign.options.reply_window_days,
                "not_before": campaign.options.not_before,
                "stop_on": list(campaign.options.stop_on),
                "allow_duplicates": campaign.options.allow_duplicates,
            },
            sort_keys=True,
        ),
        state=(
            BatchState.AWAITING_APPROVAL if approval == "review" else BatchState.SENDING
        ),
        samples=chosen,
        ignored=tuple(f"{item.key}:{item.field}" for item in campaign.ignored),
        warnings=(
            (f"{campaign.duplicates} duplicate address(es) collapsed",)
            if campaign.duplicates
            else ()
        ),
        created_at=started_at,
        submit_key=submit_key,
    )

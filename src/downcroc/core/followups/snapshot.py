from __future__ import annotations

import json
from dataclasses import dataclass

from downcroc.core.inputs.campaign_followup import parse_followups
from downcroc.core.inputs.campaign_message import parse_overrides
from downcroc.core.inputs.campaign_policy import parse_options
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.batches import Batch
from downcroc.domain.campaign import CampaignOptions, FollowUpOverride, FollowUpStep
from downcroc.domain.errors import BatchInvalid
from downcroc.store.content import ContentStore


@dataclass(frozen=True)
class ParentDeclaration:
    followups: tuple[FollowUpStep, ...]
    options: CampaignOptions
    overrides: dict[str, dict[str, FollowUpOverride]]
    source_kind: str
    template: str | None


def read_parent(
    batch: Batch,
    content: ContentStore,
    limits: IntakeLimits,
) -> ParentDeclaration:
    raw = _document(content.read_bytes(batch.source_ref))
    issues = Issues()
    campaign = _mapping(raw.get("campaign"), "campaign")
    options = parse_options(campaign.get("options", {}), issues)
    followups = parse_followups(_list(raw.get("followups")), limits, issues)
    overrides: dict[str, dict[str, FollowUpOverride]] = {}
    for index, item in enumerate(_list(raw.get("messages"))):
        message = _mapping(item, f"messages[{index}]")
        key = message.get("key")
        if not isinstance(key, str):
            continue
        overrides[key] = parse_overrides(
            message.get("followups", {}),
            f"messages[{index}]",
            issues,
            key,
        )
    issues.raise_if_any()
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    kind = source.get("kind") if isinstance(source, dict) else None
    template = source.get("template") if isinstance(source, dict) else None
    return ParentDeclaration(
        followups=tuple(followups),
        options=options,
        overrides=overrides,
        source_kind=kind if isinstance(kind, str) else batch.source_kind,
        template=template if isinstance(template, str) else None,
    )


def _document(payload: bytes) -> dict[str, object]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise BatchInvalid("the batch snapshot is not valid JSON") from error
    if not isinstance(raw, dict):
        raise BatchInvalid("the batch snapshot must be an object")
    return raw


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _mapping(value: object, where: str) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    raise BatchInvalid(f"{where} must be an object")

from __future__ import annotations

from downcroc.core.inputs.field_input import (
    MAX_KEY,
    check_keys,
    is_int,
    is_timestamp,
    mapping,
    optional_text,
    text_list,
)
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import (
    APPROVAL_MODES,
    ROUTING_MODES,
    STOP_REASONS,
    CampaignOptions,
    RoutingPolicy,
)


def parse_routing(raw: object, issues: Issues) -> RoutingPolicy:
    body = mapping(raw, "campaign.routing", issues)
    check_keys(
        body, {"mode", "account", "include", "exclude"}, "campaign.routing", issues
    )
    mode = body.get("mode", "auto")
    if mode not in ROUTING_MODES:
        issues.add(
            "invalid_field",
            f"routing.mode must be one of {sorted(ROUTING_MODES)}",
            "campaign.routing.mode",
        )
        mode = "auto"
    account = optional_text(
        body.get("account"), "campaign.routing.account", issues, limit=MAX_KEY
    )
    if mode == "fixed" and not account:
        issues.add(
            "invalid_field",
            "fixed routing needs an account",
            "campaign.routing.account",
        )
    return RoutingPolicy(
        mode=str(mode),
        account=account,
        include=text_list(body.get("include", []), "campaign.routing.include", issues),
        exclude=text_list(body.get("exclude", []), "campaign.routing.exclude", issues),
    )


def parse_options(raw: object, issues: Issues) -> CampaignOptions:
    body = mapping(raw, "campaign.options", issues)
    check_keys(
        body,
        {
            "suppress_replies",
            "reply_window_days",
            "not_before",
            "stop_on",
            "allow_duplicates",
            "approval",
        },
        "campaign.options",
        issues,
    )
    suppress_replies = body.get("suppress_replies", True)
    if not isinstance(suppress_replies, bool):
        issues.add(
            "invalid_field",
            "suppress_replies must be a boolean",
            "campaign.options.suppress_replies",
        )
        suppress_replies = True
    reply_window_days = body.get("reply_window_days", 60)
    if not is_int(reply_window_days) or not 0 <= reply_window_days <= 3650:
        issues.add(
            "invalid_field",
            "reply_window_days must be between 0 and 3650",
            "campaign.options.reply_window_days",
        )
        reply_window_days = 60
    not_before = optional_text(
        body.get("not_before"), "campaign.options.not_before", issues, limit=64
    )
    if not_before and not is_timestamp(not_before):
        issues.add(
            "invalid_field",
            "not_before must be an ISO 8601 timestamp",
            "campaign.options.not_before",
        )
    stop_on = text_list(
        body.get("stop_on", ["reply", "bounce"]), "campaign.options.stop_on", issues
    )
    unknown = [item for item in stop_on if item not in STOP_REASONS]
    if unknown:
        issues.add(
            "invalid_field",
            f"stop_on contains unknown reasons: {', '.join(unknown)}",
            "campaign.options.stop_on",
        )
    allow_duplicates = body.get("allow_duplicates", False)
    if not isinstance(allow_duplicates, bool):
        issues.add(
            "invalid_field",
            "allow_duplicates must be a boolean",
            "campaign.options.allow_duplicates",
        )
        allow_duplicates = False
    approval = body.get("approval", "review")
    if approval not in APPROVAL_MODES:
        issues.add(
            "invalid_field",
            f"approval must be one of {sorted(APPROVAL_MODES)}",
            "campaign.options.approval",
        )
        approval = "review"
    return CampaignOptions(
        suppress_replies=suppress_replies,
        reply_window_days=reply_window_days,
        not_before=not_before,
        stop_on=tuple(stop_on),
        allow_duplicates=allow_duplicates,
        approval=str(approval),
    )

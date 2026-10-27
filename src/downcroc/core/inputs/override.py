from __future__ import annotations

from dataclasses import replace

from downcroc.domain.campaign import Campaign, RoutingPolicy


def fixed_account(campaign: Campaign, account_id: str) -> Campaign:
    """Pin every message to one account, overriding the file's routing."""
    policy: RoutingPolicy = campaign.routing
    pinned = RoutingPolicy(
        mode="fixed",
        account=account_id,
        include=policy.include,
        exclude=policy.exclude,
    )
    return replace(campaign, routing=pinned)

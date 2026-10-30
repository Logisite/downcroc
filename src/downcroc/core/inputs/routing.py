from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from json import dumps

from downcroc.core.policy import PolicyResolver
from downcroc.domain.accounts import Account, AccountStatus
from downcroc.domain.campaign import Campaign, RoutingPolicy
from downcroc.domain.errors import AccountUnavailable


@dataclass(frozen=True)
class RoutingPlan:
    mode: str
    account_id: str | None
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    assignments: dict[str, str]

    def as_json(self) -> str:
        counts: dict[str, int] = {}
        for account_id in self.assignments.values():
            counts[account_id] = counts.get(account_id, 0) + 1
        return dumps(
            {
                "mode": self.mode,
                "account": self.account_id,
                "include": list(self.include),
                "exclude": list(self.exclude),
                "assignments": self.assignments,
                "counts": counts,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def resolve(
    campaign: Campaign, accounts: list[Account], policy: PolicyResolver
) -> RoutingPlan:
    routing = campaign.routing
    eligible = _eligible(routing, accounts, policy)
    if not eligible:
        raise AccountUnavailable(
            "no connected account matches the routing policy",
            hint="connect an account or widen campaign.routing",
        )
    if routing.mode == "fixed":
        chosen = _find(eligible, routing.account or "")
        if chosen is None:
            raise AccountUnavailable(
                f"account {routing.account} is not connected or is excluded",
            )
        assignments = {message.key: chosen.id for message in campaign.messages}
        return RoutingPlan(
            mode=routing.mode,
            account_id=chosen.id,
            include=routing.include,
            exclude=routing.exclude,
            assignments=assignments,
        )
    assignments = {
        message.key: _pick(campaign.key, message.key, eligible, policy).id
        for message in campaign.messages
    }
    return RoutingPlan(
        mode=routing.mode,
        account_id=None,
        include=routing.include,
        exclude=routing.exclude,
        assignments=assignments,
    )


def _eligible(
    policy: RoutingPolicy, accounts: list[Account], resolver: PolicyResolver
) -> list[Account]:
    result = []
    for account in accounts:
        if account.archived_at is not None:
            continue
        if account.status is not AccountStatus.CONNECTED:
            continue
        if not resolver.effective(account).enabled:
            continue
        if policy.include and not _matches(policy.include, account):
            continue
        if _matches(policy.exclude, account):
            continue
        result.append(account)
    return result


def _matches(names: tuple[str, ...], account: Account) -> bool:
    folded = {name.strip().casefold() for name in names}
    return account.id.casefold() in folded or account.address.casefold() in folded


def _find(accounts: list[Account], wanted: str) -> Account | None:
    key = wanted.strip().casefold()
    for account in accounts:
        if account.id.casefold() == key or account.address.casefold() == key:
            return account
    return None


def _pick(
    campaign_key: str,
    message_key: str,
    accounts: list[Account],
    resolver: PolicyResolver,
) -> Account:
    digest = hashlib.sha256(f"{campaign_key}:{message_key}".encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    weights = [
        max(1, resolver.effective(account).daily_allowance) for account in accounts
    ]
    return random.Random(seed).choices(accounts, weights=weights, k=1)[0]

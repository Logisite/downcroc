from __future__ import annotations

from collections.abc import Mapping

from downcroc.core.inbound.signals import WatcherHandle
from downcroc.core.inbound.sources import SourceChoice, choose_source
from downcroc.domain.accounts import Account
from downcroc.domain.providers import ProviderSpec
from downcroc.runtime.config.schema import InboundSettings


def plan_for(
    settings: InboundSettings,
    account: Account,
    spec: ProviderSpec,
    handles: Mapping[str, WatcherHandle],
) -> tuple[SourceChoice, bool, bool]:
    allow, denied = _idle_slot(settings, spec, handles)
    choice = choose_source(
        account,
        spec,
        settings.source,
        allow_idle=allow,
    )
    return choice, allow, denied


def _idle_slot(
    settings: InboundSettings,
    spec: ProviderSpec,
    handles: Mapping[str, WatcherHandle],
) -> tuple[bool, bool]:
    if not spec.supports_idle:
        return True, False
    cap = max(1, int(settings.idle_fleet_cap))
    used = sum(
        1
        for handle in handles.values()
        if handle.source == "imap" and handle.allow_idle and handle.mode != "imap_poll"
    )
    return used < cap, used >= cap


def select_event(
    account: Account,
    source: str,
    default: str,
) -> tuple[str, dict[str, object]]:
    was = account.inbound_source
    if was in {"imap", "gmail_api"} and was != source:
        return "inbound.source_switch", {
            "account": account.id,
            "from": was,
            "to": source,
            "backfilled": False,
        }
    return "inbound.source_selected", {
        "account": account.id,
        "source": source,
        "mode": "api_poll" if source == "gmail_api" else "idle",
        "reason": account.source_override or default,
    }


def health_rows(
    accounts: list[Account],
    handles: Mapping[str, WatcherHandle],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for account in accounts:
        handle = handles.get(account.id)
        source = (
            handle.source if handle is not None else account.inbound_source or "imap"
        )
        events = [
            moment
            for moment in (account.last_sync_at, account.last_sweep_at)
            if moment is not None
        ]
        rows.append(
            {
                "account_id": account.id,
                "address": account.address,
                "status": account.status.value,
                "owner": source,
                "mode": handle.mode if handle is not None else "stopped",
                "idle_allowed": handle.allow_idle if handle is not None else True,
                "last_connected_at": account.last_verified_at,
                "last_event_at": max(events) if events else None,
                "last_sync_at": account.last_sync_at,
                "last_sweep_at": account.last_sweep_at,
                "cursor_source": account.cursor_source,
                "uidvalidity": account.uidvalidity,
                "last_uid": account.last_uid,
                "history_id": account.history_id,
                "last_error": account.last_error,
                "consecutive_failures": account.consecutive_failures,
            }
        )
    return rows

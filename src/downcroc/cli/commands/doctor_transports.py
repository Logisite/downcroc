from __future__ import annotations

from downcroc.cli.client import get
from downcroc.cli.output import json_out, record
from downcroc.cli.ui.session import Ui


def transports(client, ui: Ui) -> int:
    body = get(client, "/api/doctor/transports")
    if ui.json_mode:
        json_out(body)
        return 0 if body.get("ok") else 1
    for binding in body["bindings"]:
        state = binding["health"]
        if binding["problem"]:
            state = f"{state} ({binding['problem']})"
        record(
            {
                "account": f"{binding['account_id']} {binding['address']}",
                "kind": binding["kind"],
                "health": state,
                "priority": binding["priority"],
                "limit": binding["max_concurrency"],
                "client": binding["oauth_client_id"] or "-",
            }
        )
    for client_row in body["clients"]:
        record(
            {
                "client": client_row["id"],
                "provider": client_row["provider_id"],
                "project": client_row["project_id"] or "-",
                "client_id": client_row["client_id"],
            }
        )
    failed = [check for check in body.get("checks", []) if not check["ok"]]
    for check in failed:
        record(
            {
                "account": check["account_id"],
                "binding": check["binding_id"] or "-",
                "check": check["check"],
                "code": check["code"],
                "detail": check.get("detail") or "-",
            }
        )
    print(
        ui.result(
            bool(body.get("ok")),
            "transports healthy" if body.get("ok") else "transports need attention",
        )
    )
    return 0 if body.get("ok") else 1


def inbound(client, ui: Ui) -> int:
    body = get(client, "/api/doctor/inbound")
    if ui.json_mode:
        json_out(body)
        return 0 if body.get("ok") else 1
    record(
        {
            "sources": body.get("sources", {}),
            "stale": body.get("stale", 0),
            "idle_cap": body.get("idle_fleet_cap"),
        }
    )
    for row in body["accounts"]:
        if row["owner"] == "gmail_api":
            cursor = row.get("history_id") or "-"
        else:
            cursor = f"{row.get('uidvalidity', 0)}/{row.get('last_uid', 0)}"
        record(
            {
                "account": f"{row['account_id']} {row['address']}",
                "inbound": f"{row['owner']} {row['mode']}",
                "cursor": cursor,
                "connected": row.get("last_connected_at") or "-",
                "event": row.get("last_event_at") or "-",
                "last_sync": row.get("last_sync_at") or "-",
                "last_sweep": row.get("last_sweep_at") or "-",
                "failures": row.get("consecutive_failures", 0),
                "error": row.get("last_error") or "-",
                "idle_cap": "yes" if not row.get("idle_allowed", True) else "no",
            }
        )
    print(
        ui.result(
            bool(body.get("ok")),
            "inbound healthy" if body.get("ok") else "inbound needs attention",
        )
    )
    return 0 if body.get("ok") else 1


def capacity(client, ui: Ui) -> int:
    body = get(client, "/api/doctor/capacity")
    if ui.json_mode:
        json_out(body)
        return 0 if body.get("ok") else 1
    record(
        {
            "lanes": body["lanes"],
            "api_lanes": body["api_lanes"],
            "smtp_seats": body["smtp_seats"],
            "serial": "yes" if body["serial"] else "no",
            "parallel_sends": "on" if body["parallel_sends"] else "off",
            "configured_seats": body["configured_smtp_seats"],
            "bindings": body["bindings_per_kind"],
        }
    )
    record(
        {
            "active_slots": len(body.get("smtp_active", [])),
            "queue": len(body.get("smtp_queue", [])),
            "waiting": len(body.get("smtp_waiting", [])),
            "password": body.get("password_accounts", 0),
            "oauth": body.get("oauth_accounts", 0),
            "oauth_api_only": body.get("oauth_api_only", 0),
            "password_waiting": body.get("password_waiting", 0),
            "reserved_units": body.get("reserved_units", 0),
            "held_pinned": body.get("held_pinned", 0),
        }
    )
    for row in body["smtp_only"]:
        print(f"  smtp only: {row['account_id']} {row['address']}")
    for account_id in body.get("smtp_waiting", []):
        print(f"  waiting for a slot: {account_id}")
    for row in body.get("paused_accounts", []):
        print(
            f"  paused: {row['account_id']} {row['address']} "
            f"since {row['since']} ({row['reason'] or 'no reason'})"
        )
    for row in body.get("idle_seats", []):
        print(f"  idle seat: {row['account_id']} {row['binding_id']} {row['kind']}")
    if body.get("warning"):
        tone = "bad" if body.get("risk") == "critical" else "warn"
        print(ui.paint(body["warning"], tone))
    if body.get("recommendation"):
        print(ui.paint(body["recommendation"], "note"))
    return 0 if body.get("ok") else 1

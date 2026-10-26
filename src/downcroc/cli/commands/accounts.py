from __future__ import annotations

import getpass
import sys
import time

from downcroc.cli.client import CliError, api, delete, get, patch, post
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record, table


def _password(stdin: bool) -> str:
    if stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("App password: ")
    if not password:
        raise SystemExit("a password is required")
    return password


def _list(rows: list[dict]) -> None:
    table(
        ["id", "address", "provider", "status", "credential", "watcher", "error"],
        [
            [
                item["id"],
                item["address"],
                item["provider"],
                item["status"],
                item["credential_present"],
                item["watcher_enabled"],
                item["last_error"],
            ]
            for item in rows
        ],
    )


def _show(account: dict) -> None:
    record(
        {
            "id": account["id"],
            "provider": account["provider"],
            "address": account["address"],
            "label": account["label"],
            "status": account["status"],
            "credential": account["credential_present"],
            "watcher": account["watcher_enabled"],
            "created_at": account["created_at"],
            "last_verified_at": account["last_verified_at"],
            "last_error": account["last_error"],
        }
    )
    record(
        {
            "last_uid": account["sync"]["last_uid"],
            "uidvalidity": account["sync"]["uidvalidity"],
            "last_sync_at": account["sync"]["last_sync_at"],
            "failures": account["sync"]["consecutive_failures"],
            "allowance": account["quota"]["daily_allowance"],
            "window": (
                f"{account['quota']['window_start']}..{account['quota']['window_end']}"
            ),
            "in_flight": account["quota"]["max_in_flight"],
        }
    )


def _providers(rows: list[dict]) -> None:
    table(
        ["id", "label", "auth", "imap", "smtp", "oauth"],
        [
            [
                item["id"],
                item["label"],
                item["auth_kind"],
                f"{item['imap_host']}:{item['imap_port']}",
                f"{item['smtp_host']}:{item['smtp_port']}",
                item["oauth_configured"],
            ]
            for item in rows
        ],
    )


def _wait(client, account_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        account = get(client, f"/api/accounts/{account_id}")
        if account["status"] in {"connected", "needs_reauth"}:
            return account
        time.sleep(0.5)
    raise CliError("timed out waiting for the account to connect")


def run(args: object) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if args.action == "list":
            rows = get(client, "/api/accounts")
            if args.json:
                json_out(rows)
            else:
                _list(rows)
            return 0
        if args.action == "providers":
            rows = get(client, "/api/providers")
            if args.json:
                json_out(rows)
            else:
                _providers(rows)
            return 0
        if args.action == "add":
            account = post(
                client,
                "/api/accounts",
                {
                    "provider": args.provider,
                    "address": args.address,
                    "label": args.label,
                },
            )
            if args.json:
                json_out(account)
            else:
                print(f"created {account['id']} ({account['status']})")
            return 0
        if args.action == "delete":
            if not args.yes:
                if not sys.stdin.isatty():
                    raise CliError("refusing to delete without --yes")
                answer = input(f"delete {args.account_id}? [y/N] ")
                if answer.strip().lower() not in {"y", "yes"}:
                    print("cancelled")
                    return 1
            delete(client, f"/api/accounts/{args.account_id}")
            print(f"deleted {args.account_id}")
            return 0
        if args.action == "attempt":
            attempt = post(
                client,
                f"/api/accounts/{args.account_id}/attempts",
            )
            if not args.json:
                print(f"open {attempt['authorization_url']}")
                print(f"attempt expires at {attempt['expires_at']}")
            if not args.wait:
                if args.json:
                    json_out(attempt)
                return 0
            account = _wait(client, args.account_id, args.timeout)
            if args.json:
                json_out(account)
            else:
                _show(account)
            return 0
        if args.action == "connect":
            account = post(
                client,
                f"/api/accounts/{args.account_id}/connect",
                {"password": _password(args.password_stdin)},
            )
            if args.json:
                json_out(account)
            else:
                _show(account)
            return 0
        if args.action == "verify":
            account = post(
                client,
                f"/api/accounts/{args.account_id}/verify",
                None,
                refresh="true" if args.refresh else None,
            )
            if args.json:
                json_out(account)
            else:
                _show(account)
            return 0
        if args.action == "sync":
            account = post(client, f"/api/accounts/{args.account_id}/sync")
            if args.json:
                json_out(account)
            else:
                print(f"sync requested for {account['address']}")
            return 0
        if args.action == "watch":
            account = patch(
                client,
                f"/api/accounts/{args.account_id}/watcher",
                {"enabled": bool(args.enabled)},
            )
            if args.json:
                json_out(account)
            else:
                state = "enabled" if account["watcher_enabled"] else "disabled"
                print(f"watcher {state} for {account['address']}")
            return 0
        account = get(client, f"/api/accounts/{args.account_id}")
        if args.json:
            json_out(account)
        else:
            _show(account)
        return 0

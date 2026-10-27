from __future__ import annotations

import sys
import time

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, patch, post, put
from downcroc.cli.commands.providers import show_list
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui, build

HOST_FLAGS = {
    "imap_host": "imap_host",
    "imap_port": "imap_port",
    "imap_tls": "imap_tls",
    "smtp_host": "smtp_host",
    "smtp_port": "smtp_port",
    "smtp_tls": "smtp_tls",
}

MAX_ATTEMPTS = 3


def _list(rows: list[dict], ui: Ui) -> None:
    table(
        ["id", "address", "provider", "status", "credential", "watcher", "error"],
        [
            [
                item["id"],
                item["address"],
                item["provider"],
                item["status"],
                "yes" if item["credential_present"] else "no",
                "on" if item["watcher_enabled"] else "off",
                item["last_error"],
            ]
            for item in rows
        ],
    )
    attention = [item for item in rows if item["status"] != "connected"]
    for item in attention:
        print()
        print(
            f"{item['id']} is {item['status']}: run downcroc account connect {item['id']}"
        )
    if not ui.quiet:
        print()
        print("next: downcroc account add --provider gmail --address you@example.com")


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


def _password(args: object, ui: Ui, *, flag: str = "--password-stdin") -> str:
    path = getattr(args, "password_file", None)
    if path:
        return path_tools.read_secret(path)
    if getattr(args, "password_stdin", False):
        return path_tools.read_secret_stdin()
    if not sys.stdin.isatty():
        raise no_terminal(flag)
    return prompts.ask_secret("App password", ui=ui, flag=flag)


def _host_values(args: object) -> dict:
    return {
        key: getattr(args, key, None)
        for key in HOST_FLAGS
        if getattr(args, key, None) is not None
    }


def _choose_account(client, ui: Ui, verb: str) -> str:
    rows = get(client, "/api/accounts")
    if not rows:
        raise CliError(
            "no accounts are configured",
            code="usage",
            hint="run downcroc account add",
            exit_code=2,
        )
    chosen = prompts.choose(
        f"Account to {verb}",
        [
            prompts.Option(row["address"], row["id"], row["status"])
            for row in rows
        ],
        ui=ui,
        back=False,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _choose_provider(client, ui: Ui) -> str:
    rows = get(client, "/api/providers")
    options = [
        prompts.Option(
            row["label"],
            row["id"],
            detail=row["id"]
            if row["ready"]
            else "needs setup: " + ", ".join(row["missing"]),
        )
        for row in rows
    ]
    chosen = prompts.choose("provider", options, ui=ui, back=False)
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _add(client, args: object, ui: Ui) -> dict:
    if not args.provider:
        args.provider = _choose_provider(client, ui)
    if not args.address:
        args.address = prompts.ask("Mailbox address", ui=ui, field="--address")
    hosts = _host_values(args)
    if hosts:
        hosts["label"] = getattr(args, "label", None) or args.provider
        if args.oauth_client_id:
            hosts["oauth_client_id"] = args.oauth_client_id
        if getattr(args, "oauth_tenant", None):
            hosts["oauth_tenant"] = args.oauth_tenant
        secret = getattr(args, "password_file", None)
        if secret and args.oauth_client_id:
            hosts["oauth_client_secret"] = path_tools.read_secret(secret)
        put(client, f"/api/providers/{args.provider}", hosts)
    return post(
        client,
        "/api/accounts",
        {
            "provider": args.provider,
            "address": args.address,
            "label": args.label,
        },
    )


def _connect_password(
    client, account: dict, provider: dict, args: object, ui: Ui
) -> dict:
    failures = 0
    endpoint = f"{provider['imap_host']}:{provider['imap_port']}"
    while True:
        password = _password(args, ui)
        if not ui.json_mode:
            print(f"checking {endpoint} ...", file=sys.stderr)
        started = time.monotonic()
        try:
            account = post(
                client,
                f"/api/accounts/{account['id']}/connect",
                {"password": password},
            )
            if not ui.json_mode:
                elapsed = time.monotonic() - started
                print(f"  {elapsed:.1f}s", file=sys.stderr)
            return account
        except CliError as error:
            failures += 1
            if ui.json_mode:
                raise
            print(ui.result(False, error.label), file=sys.stderr)
            if error.hint:
                print(f"  hint: {error.hint}", file=sys.stderr)
            if failures >= MAX_ATTEMPTS:
                raise CliError(
                    f"still not connected after {MAX_ATTEMPTS} attempts",
                    code=error.code,
                    hint="the provider may lock the mailbox after repeated failures; "
                    "wait, then try `downcroc account connect` once",
                ) from error
            if not ui.interactive:
                raise
            choice = prompts.choose(
                "what next",
                [
                    prompts.Option("Retry", "retry", "enter the password again"),
                    prompts.Option("Stop", "stop", "leave the account pending"),
                ],
                ui=ui,
            )
            if choice != "retry":
                raise CliError("not connected, nothing was stored", code="cancelled")
        finally:
            args.password_stdin = False
            args.password_file = None


def _wait(client, account_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        account = get(client, f"/api/accounts/{account_id}")
        if account["status"] in {"connected", "needs_reauth"}:
            return account
        time.sleep(0.5)
    raise CliError(
        "timed out waiting for the account to connect",
        code="connect_timeout",
        hint="finish the browser sign-in, then run downcroc account verify",
    )


def _connect_oauth(client, account: dict, args: object, ui: Ui) -> dict:
    attempt = post(client, f"/api/accounts/{account['id']}/attempts")
    if not ui.json_mode:
        print(f"open {attempt['authorization_url']}", file=sys.stderr)
        print(
            f"the link expires at {attempt['expires_at']}",
            file=sys.stderr,
        )
    account = _wait(client, account["id"], args.timeout)
    if account["status"] != "connected":
        raise CliError(
            "the browser sign-in did not finish",
            code="oauth_incomplete",
            hint="run downcroc account connect again",
        )
    return account


def _connected(account: dict, ui: Ui) -> None:
    if ui.json_mode:
        json_out(account)
        return
    record(
        {
            "account": f"{account['id']} {account['address']}",
            "status": account["status"],
            "watcher": "on" if account["watcher_enabled"] else "off",
        }
    )
    print(ui.result(True, "connected"))


def run(args: object) -> int:
    paths, _, _ = load()
    ui = build(args)
    action = getattr(args, "action", None)
    if action is None:
        if ui.interactive:
            from downcroc.cli.ui.menus import accounts_menu

            accounts_menu(ui)
            return 0
        action = "list"
    with api(paths) as client:
        if action in {
            "show",
            "delete",
            "attempt",
            "connect",
            "verify",
            "sync",
            "watch",
        } and not getattr(args, "account_id", None):
            if not ui.interactive:
                raise CliError(
                    f"account {action} needs an account id",
                    code="usage",
                    exit_code=2,
                )
            args.account_id = _choose_account(client, ui, action)
        if action in {"list", "home"}:
            return _listing(client, args, ui)
        if action == "providers":
            rows = get(client, "/api/providers")
            if ui.json_mode:
                json_out(rows)
                return 0
            show_list(rows, ui)
            return 0
        if action == "add":
            account = _add(client, args, ui)
            return _added(account, ui)
        if action == "delete":
            return _delete(client, args, ui)
        if action == "attempt":
            return _attempt(client, args, ui)
        if action == "connect":
            return _connect(client, args, ui)
        if action == "verify":
            account = post(
                client,
                f"/api/accounts/{args.account_id}/verify",
                None,
                refresh="true" if args.refresh else None,
            )
            if ui.json_mode:
                json_out(account)
            else:
                _show(account)
                print(ui.result(True, "verified"))
            return 0
        if action == "sync":
            account = post(client, f"/api/accounts/{args.account_id}/sync")
            if ui.json_mode:
                json_out(account)
            else:
                record({"sync": f"requested for {account['address']}"})
            return 0
        if action == "watch":
            return _watch(client, args, ui)
        account = get(client, f"/api/accounts/{args.account_id}")
        if ui.json_mode:
            json_out(account)
        else:
            _show(account)
        return 0


def _listing(client, args: object, ui: Ui) -> int:
    rows = get(client, "/api/accounts")
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print("no accounts yet")
        if not ui.quiet:
            print(
                "next: downcroc account add --provider gmail --address you@example.com"
            )
        return 0
    _list(rows, ui)
    return 0


def _added(account: dict, ui: Ui) -> int:
    if ui.json_mode:
        json_out(account)
        return 0
    record(
        {
            "account": f"{account['id']} {account['address']}",
            "status": account["status"],
        }
    )
    print(f"next: downcroc account connect {account['id']}")
    return 0


def _delete(client, args: object, ui: Ui) -> int:
    confirmed = getattr(args, "yes", False) or prompts.confirm(
        f"delete {args.account_id} and its stored credential?",
        ui=ui,
        default=False,
    )
    if not confirmed:
        raise CliError("cancelled", code="cancelled")
    delete(client, f"/api/accounts/{args.account_id}")
    if ui.json_mode:
        json_out({"deleted": args.account_id})
    else:
        record({"account": f"{args.account_id} deleted"})
    return 0


def _attempt(client, args: object, ui: Ui) -> int:
    attempt = post(client, f"/api/accounts/{args.account_id}/attempts")
    if not ui.json_mode:
        print(f"open {attempt['authorization_url']}")
        print(f"the link expires at {attempt['expires_at']}")
    if not args.wait:
        if ui.json_mode:
            json_out(attempt)
        return 0
    account = _wait(client, args.account_id, args.timeout)
    if ui.json_mode:
        json_out(account)
    else:
        _show(account)
        print(ui.result(True, "connected"))
    return 0


def connect_now(client, account: dict, args: object, ui: Ui) -> dict:
    provider = get(client, f"/api/providers/{account['provider']}")
    if provider["auth_kind"] == "oauth2":
        return _connect_oauth(client, account, args, ui)
    if not provider["ready"]:
        raise CliError(
            "the provider is not ready",
            code="provider_not_ready",
            hint=f"run downcroc provider edit {provider['id']}",
            fields={"missing": ", ".join(provider["missing"])},
        )
    return _connect_password(client, account, provider, args, ui)


def _connect(client, args: object, ui: Ui) -> int:
    account = get(client, f"/api/accounts/{args.account_id}")
    updated = connect_now(client, account, args, ui)
    _connected(updated, ui)
    return 0


def _watch(client, args: object, ui: Ui) -> int:
    desired = args.enabled
    if desired is None:
        if not ui.interactive:
            raise CliError(
                "choose --on or --off",
                code="usage",
                exit_code=2,
            )
        desired = prompts.confirm("enable the inbound watcher?", ui=ui, default=True)
    account = patch(
        client,
        f"/api/accounts/{args.account_id}/watcher",
        {"enabled": bool(desired)},
    )
    if ui.json_mode:
        json_out(account)
    else:
        state = "enabled" if account["watcher_enabled"] else "disabled"
        record({"watcher": f"{state} for {account['address']}"})
    return 0

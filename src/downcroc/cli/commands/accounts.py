from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, patch, post, put
from downcroc.cli.commands import account_transport, account_view
from downcroc.cli.commands.account_connect import (
    connect_now,
    connected,
    wait,
)
from downcroc.cli.commands.policy import account_policy
from downcroc.cli.commands.providers import show_list
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record
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

__all__ = ["connect_now", "run"]


def _host_values(args: object) -> dict:
    return {
        key: getattr(args, key, None)
        for key in HOST_FLAGS
        if getattr(args, key, None) is not None
    }


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
            "deletion",
            "archive",
            "unarchive",
            "attempt",
            "connect",
            "verify",
            "sync",
            "watch",
            "policy",
        } and not getattr(args, "account_id", None):
            if not ui.interactive:
                raise CliError(
                    f"account {action} needs an account id",
                    code="usage",
                    exit_code=2,
                )
            args.account_id = account_view.choose_account(client, ui, action)
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
            return account_view.added(account, ui)
        if action == "delete":
            return _delete(client, args, ui)
        if action == "deletion":
            return _deletion(client, args, ui)
        if action == "archive":
            return _archive(client, args, ui, archived=True)
        if action == "unarchive":
            return _archive(client, args, ui, archived=False)
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
                account_view.show(account)
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
        if action == "transport":
            return account_transport.run(client, args, ui)
        if action == "policy":
            return account_policy(client, args, ui)
        account = get(client, f"/api/accounts/{args.account_id}")
        if ui.json_mode:
            json_out(account)
        else:
            account_view.show(account)
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
    account_view.listing(rows, ui)
    return 0


def _delete(client, args: object, ui: Ui) -> int:
    account_id = args.account_id
    preview = get(client, f"/api/accounts/{account_id}/deletion")
    if args.dry_run:
        if ui.json_mode:
            json_out(preview)
        else:
            account_view.deletion_view(preview)
        return 0
    if not ui.json_mode:
        account_view.deletion_view(preview)
    prompts.confirm(
        f"delete {account_id} and its stored credential?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )
    result = delete(
        client,
        f"/api/accounts/{account_id}",
        confirm="true",
        reassign_to=args.reassign_to,
        force_jobs="true" if args.force_jobs else None,
        force_history="true" if args.force_history else None,
    )
    if ui.json_mode:
        json_out(result)
    else:
        record(
            {
                "account": f"{result['account_id']} deleted",
                "reassigned": result["reassigned"],
                "deleted_jobs": result["deleted_jobs"],
            }
        )
    return 0


def _deletion(client, args: object, ui: Ui) -> int:
    preview = get(client, f"/api/accounts/{args.account_id}/deletion")
    if ui.json_mode:
        json_out(preview)
    else:
        account_view.deletion_view(preview)
    return 0


def _archive(client, args: object, ui: Ui, *, archived: bool) -> int:
    action = "archive" if archived else "unarchive"
    prompts.confirm(
        f"{action} {args.account_id}?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )
    account = post(
        client, f"/api/accounts/{args.account_id}/{action}", None, confirm="true"
    )
    if ui.json_mode:
        json_out(account)
    else:
        record(
            {
                "account": f"{account['id']} {account['address']}",
                "archived": account["archived_at"] or "no",
            }
        )
    return 0


def _attempt(client, args: object, ui: Ui) -> int:
    params = {}
    if getattr(args, "client", None):
        params["client_id"] = args.client
    attempt = post(client, f"/api/accounts/{args.account_id}/attempts", **params)
    if not ui.json_mode:
        print(f"open {attempt['authorization_url']}")
        print(f"the link expires at {attempt['expires_at']}")
    if not args.wait:
        if ui.json_mode:
            json_out(attempt)
        return 0
    account = wait(client, args.account_id, args.timeout)
    if ui.json_mode:
        json_out(account)
    else:
        account_view.show(account)
        print(ui.result(True, "connected"))
    return 0


def _connect(client, args: object, ui: Ui) -> int:
    account = get(client, f"/api/accounts/{args.account_id}")
    updated = connect_now(client, account, args, ui)
    connected(updated, ui)
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

from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import DEFAULT_TIMEOUT_S, api, delete, get, patch, post, put
from downcroc.cli.commands import account_transport, account_view, oauth_setup
from downcroc.cli.commands.account_connect import (
    connect_now,
    connected,
    expires_in,
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
            detail=_provider_detail(row),
        )
        for row in rows
    ]
    chosen = prompts.choose("provider", options, ui=ui, back=False)
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _provider_detail(row: dict) -> str:
    if not row["ready"]:
        return "needs setup: " + ", ".join(row["missing"])
    if row["auth_kind"] == "oauth2":
        return "browser sign-in, recommended"
    return "app password"


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
    try:
        return post(
            client,
            "/api/accounts",
            {
                "provider": args.provider,
                "address": args.address,
                "label": args.label,
            },
        )
    except CliError as error:
        if error.code != "account_exists" or not ui.interactive:
            raise
        existing = _find_account(client, args.address)
        if existing is None:
            raise
        if not prompts.confirm(
            "That address already exists. Use the existing mailbox?",
            ui=ui,
            default=True,
        ):
            raise
        if (
            existing["status"] == "connected"
            and args.provider == "gmail"
            and prompts.confirm(
                "Add a Gmail API binding to this mailbox?",
                ui=ui,
                default=True,
            )
        ):
            provider = get(client, "/api/providers/gmail")
            if not provider["ready"]:
                oauth_setup.import_client(ui)
            post(
                client,
                f"/api/accounts/{existing['id']}/transports",
                {"kind": "gmail_api"},
            )
        return existing


def _find_account(client, address: str) -> dict | None:
    wanted = address.strip().lower()
    return next(
        (
            item
            for item in get(client, "/api/accounts")
            if item["address"].lower() == wanted
        ),
        None,
    )


def _timeout(args: object, settings) -> float:
    given = getattr(args, "timeout", None)
    if given is not None:
        return float(given)
    if (
        getattr(args, "action", None) == "transport"
        and getattr(args, "transport_action", None) == "test"
    ):
        probe = max(
            settings.outbound.smtp_timeout_s,
            settings.outbound.api_timeout_s,
        )
        return probe + 5.0
    return DEFAULT_TIMEOUT_S


def run(args: object) -> int:
    paths, settings, _ = load()
    ui = build(args)
    action = getattr(args, "action", None)
    if action is None:
        if ui.interactive:
            from downcroc.cli.ui.tree import open_path

            open_path(ui, ("account",))
            return 0
        action = "list"
    with api(paths, timeout=_timeout(args, settings)) as client:
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
            "inbound",
            "policy",
        } and not getattr(args, "account_id", None):
            if not ui.interactive:
                raise CliError(
                    f"account {action} needs an account id",
                    code="usage",
                    exit_code=2,
                )
            args.account_id = account_view.choose_account(
                client,
                ui,
                action,
                archived=action == "unarchive",
            )
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
            account_view.added(account, ui, hint=not ui.interactive)
            return _offer_connect(client, account, args, ui)
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
                account_view.transports(client, account["id"], ui)
                print(ui.result(True, "verified"))
            return 0
        if action == "sync":
            account = post(client, f"/api/accounts/{args.account_id}/sync")
            if ui.json_mode:
                json_out(account)
            else:
                record(
                    {
                        "sync": f"requested for {account['address']}",
                        "inbound": (
                            f"{account['inbound']['owner']} "
                            f"{account['inbound']['mode']}"
                        ),
                        "cursor": (
                            account["inbound"]["history_id"]
                            or (
                                f"{account['sync']['uidvalidity']}/"
                                f"{account['sync']['last_uid']}"
                            )
                        ),
                    }
                )
            return 0
        if action == "inbound":
            account = patch(
                client,
                f"/api/accounts/{args.account_id}/inbound",
                {"source": args.source},
            )
            if ui.json_mode:
                json_out(account)
            else:
                record(
                    {
                        "account": f"{account['id']} {account['address']}",
                        "inbound": (
                            f"{account['inbound']['owner']} "
                            f"{account['inbound']['mode']}"
                        ),
                        "override": account["inbound"]["override"] or "auto",
                    }
                )
            return 0
        if action in {"pause", "resume"}:
            return _hold_accounts(client, args, ui, action)
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
            account_view.transports(client, account["id"], ui)
        return 0


def _listing(client, args: object, ui: Ui) -> int:
    archived = bool(getattr(args, "archived", False))
    rows = get(client, "/api/accounts", archived="true" if archived else None)
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print("no archived accounts" if archived else "no accounts yet")
        if not ui.quiet and not archived:
            print(
                "next: downcroc account add --provider gmail --address you@example.com"
            )
        return 0
    account_view.listing(rows, ui, archived=archived)
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
        print(f"the link expires in {expires_in(attempt)}")
    if not args.wait:
        if ui.json_mode:
            json_out(attempt)
        return 0
    if getattr(args, "redirect_url", None):
        oauth_setup.deliver_redirect(args.redirect_url)
    account = wait(client, args.account_id, args.timeout, attempt.get("id"))
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


def _offer_connect(client, account: dict, args: object, ui: Ui) -> int:
    if not ui.interactive or account["status"] != "pending":
        return 0
    provider = get(client, f"/api/providers/{account['provider']}")
    question = (
        "Open the browser sign-in for this mailbox now?"
        if provider["auth_kind"] == "oauth2"
        else "Enter the app password for this mailbox now?"
    )
    if not prompts.confirm(question, ui=ui, default=True):
        print(f"next: downcroc account connect {account['id']}")
        return 0
    try:
        updated = connect_now(client, account, args, ui)
    except CliError as error:
        print(ui.result(False, error.label))
        if error.hint:
            print(f"  hint: {error.hint}")
        print(f"resume with: downcroc account connect {account['id']}")
        return 0
    connected(updated, ui)
    return 0


def _hold_accounts(client, args: object, ui: Ui, action: str) -> int:
    rows = []
    failed = False
    for account_id in args.account_id:
        try:
            body = {"reason": getattr(args, "reason", None)}
            result = post(
                client,
                f"/api/accounts/{account_id}/{action}",
                body,
            )
            rows.append(result)
        except CliError as error:
            failed = True
            rows.append({"account_id": account_id, "error": error.label})
    if ui.json_mode:
        json_out(rows)
        return 1 if failed else 0
    for row in rows:
        if "error" in row:
            print(ui.result(False, row["error"], row["account_id"]))
            continue
        account = row["account"]
        record(
            {
                "account": f"{account['id']} {account['address']}",
                "sending": "paused" if action == "pause" else "running",
                "changed": row.get("changed"),
            }
        )
        advice = (row.get("impact") or {}).get("advice")
        if advice:
            print(ui.paint(advice, "warn"))
    return 1 if failed else 0


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

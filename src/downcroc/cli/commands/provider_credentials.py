from __future__ import annotations

from downcroc.cli import paths as path_tools
from downcroc.cli.client import api, delete, get, post
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, no_terminal
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui


def choose_provider(client, ui: Ui, title: str) -> str:
    rows = get(client, "/api/providers")
    chosen = prompts.choose(
        title,
        [
            prompts.Option(
                row["label"],
                row["id"],
                "ready" if row["ready"] else "needs setup",
            )
            for row in rows
        ],
        ui=ui,
        back=False,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def run(args: object, ui: Ui) -> int:
    action = getattr(args, "credential_action", None)
    if action is None and ui.interactive:
        return _menu(ui)
    if action == "set":
        return _set(args, ui)
    if action == "show":
        return _show(args, ui)
    if action == "remove":
        return _remove(args, ui)
    return _list(args, ui)


def _set(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if not getattr(args, "provider_id", None):
            args.provider_id = choose_provider(client, ui, "Provider for this client")
        path = getattr(args, "client", None)
        if not path:
            if not ui.interactive:
                raise no_terminal("--client")
            path = prompts.ask("Client JSON path", ui=ui, field="--client")
        payload = path_tools.read_text(path, field="--client")
        client_row = post(
            client,
            "/api/oauth-clients",
            {
                "provider_id": args.provider_id,
                "payload": payload,
                "label": getattr(args, "label", None) or "",
            },
        )
    if ui.json_mode:
        json_out(client_row)
        return 0
    record(
        {
            "client": client_row["id"],
            "provider": client_row["provider_id"],
            "label": client_row["label"],
        }
    )
    if client_row["project_id"]:
        record({"project": client_row["project_id"]})
    return 0


def _list(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    params = {}
    if getattr(args, "provider_id", None):
        params["provider_id"] = args.provider_id
    with api(paths) as client:
        rows = get(client, "/api/oauth-clients", **params)
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print(ui.dim("no oauth clients imported"))
        return 0
    table(
        ["client", "provider", "label", "project", "created"],
        [
            [
                row["id"],
                row["provider_id"],
                row["label"],
                row["project_id"] or "",
                row["created_at"],
            ]
            for row in rows
        ],
    )
    return 0


def _show(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if not getattr(args, "client_id", None):
            args.client_id = _pick(client, ui, "Client")
        client_row = get(client, f"/api/oauth-clients/{args.client_id}")
        dependents = get(
            client,
            f"/api/oauth-clients/{args.client_id}/dependents",
        )
    if ui.json_mode:
        json_out({"client": client_row, "dependents": dependents})
        return 0
    record(
        {
            "client": client_row["id"],
            "provider": client_row["provider_id"],
            "label": client_row["label"],
            "client_id": client_row["client_id"],
            "project": client_row["project_id"] or "not set",
        }
    )
    if dependents:
        print()
        table(
            ["binding", "account", "address", "kind", "health"],
            [
                [
                    row["binding_id"],
                    row["account_id"],
                    row["address"],
                    row["kind"],
                    row["health"],
                ]
                for row in dependents
            ],
        )
    return 0


def _remove(args: object, ui: Ui) -> int:
    paths, _, _ = load()
    with api(paths) as client:
        if not getattr(args, "client_id", None):
            args.client_id = _pick(client, ui, "Client to remove")
        dependents = get(
            client,
            f"/api/oauth-clients/{args.client_id}/dependents",
        )
        if dependents and not getattr(args, "force", False):
            raise CliError(
                "bindings still use this client",
                code="oauth_client_in_use",
                hint="pass --force to move them to reauth",
            )
        confirmed = getattr(args, "yes", False) or prompts.confirm(
            f"Remove client {args.client_id}?",
            ui=ui,
            default=False,
        )
        if not confirmed:
            raise CliError("cancelled", code="cancelled")
        removed = delete(
            client,
            f"/api/oauth-clients/{args.client_id}",
            confirm=True,
            force=getattr(args, "force", False),
        )
    if ui.json_mode:
        json_out(removed)
    else:
        record({"client": f"{args.client_id} removed"})
    return 0


def _pick(client, ui: Ui, title: str) -> str:
    rows = get(client, "/api/oauth-clients")
    if not rows:
        raise CliError("no oauth clients imported", code="oauth_client_missing")
    chosen = prompts.choose(
        title,
        [prompts.Option(row["label"], row["id"], row["provider_id"]) for row in rows],
        ui=ui,
        back=False,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _menu(ui: Ui) -> int:
    chosen = prompts.choose(
        "OAuth clients",
        [
            prompts.Option("import a client", "set", "Google client JSON"),
            prompts.Option("list clients", "list"),
            prompts.Option("show one", "show"),
            prompts.Option("remove one", "remove"),
        ],
        ui=ui,
        back=True,
    )
    if chosen is None:
        return 0
    return run(_MenuArgs(str(chosen)), ui)


class _MenuArgs:
    def __init__(self, action: str) -> None:
        self.credential_action = action
        self.provider_id = None
        self.client_id = None
        self.client = None
        self.label = None
        self.force = False
        self.yes = False

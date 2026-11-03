from __future__ import annotations

from downcroc.cli.client import delete, get, patch, post
from downcroc.cli.commands import account_view
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, record, table
from downcroc.cli.ui import prompts
from downcroc.cli.ui.session import Ui

KINDS = [
    prompts.Option("SMTP", "smtp", "a stable authenticated seat"),
    prompts.Option("Gmail API", "gmail_api", "HTTPS lanes, configurable concurrency"),
]

FIELDS = [
    prompts.Option("Priority", "priority", "higher is tried first"),
    prompts.Option("Concurrency", "max_concurrency", "parallel API sends"),
    prompts.Option("Rate limit", "rate_per_min", "API calls per minute"),
    prompts.Option("Enabled", "enabled", "turn the transport on or off"),
]


def run(client, args: object, ui: Ui) -> int:
    action = getattr(args, "transport_action", None)
    if action is None:
        if not ui.interactive:
            action = "list"
        else:
            action = _choose_action(ui)
    account_id = getattr(args, "account_id", None) or account_view.choose_account(
        client, ui, "manage transports for"
    )
    if action == "list":
        return _list(client, account_id, ui)
    if action == "add":
        return _add(client, account_id, args, ui)
    if action == "set":
        return _set(client, account_id, args, ui)
    if action == "remove":
        return _remove(client, account_id, args, ui)
    if action == "test":
        return _test(client, account_id, args, ui)
    raise CliError(f"unknown transport action {action}", code="usage", exit_code=2)


def _choose_action(ui: Ui) -> str:
    chosen = prompts.choose(
        "Transport action",
        [
            prompts.Option("List", "list", "show the send transports"),
            prompts.Option("Add", "add", "attach another send mechanism"),
            prompts.Option("Change", "set", "tune priority, lanes, or state"),
            prompts.Option("Remove", "remove", "detach a send mechanism"),
            prompts.Option("Test", "test", "probe it right now"),
        ],
        ui=ui,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _bindings(client, account_id: str) -> list[dict]:
    return get(client, f"/api/accounts/{account_id}/transports")


def _list(client, account_id: str, ui: Ui) -> int:
    rows = _bindings(client, account_id)
    if ui.json_mode:
        json_out(rows)
        return 0
    if not rows:
        print("this mailbox has no send transports")
        if not ui.quiet:
            print(f"next: downcroc account transport add {account_id} --kind smtp")
        return 0
    table(
        ["id", "kind", "slot", "priority", "health", "lanes", "rate", "error"],
        [
            [
                item["id"],
                item["kind"],
                item.get("slot") or "-",
                item["priority"],
                item["health"],
                item["max_concurrency"],
                item["rate_per_min"] or "-",
                item["last_error_code"] or "-",
            ]
            for item in rows
        ],
    )
    return 0


def _choose_binding(client, account_id: str, ui: Ui, verb: str) -> str:
    rows = _bindings(client, account_id)
    if not rows:
        raise CliError(
            "this mailbox has no send transports",
            code="usage",
            hint=f"run downcroc account transport add {account_id}",
            exit_code=2,
        )
    chosen = prompts.choose(
        f"Transport to {verb}",
        [prompts.Option(item["kind"], item["id"], item["health"]) for item in rows],
        ui=ui,
        back=False,
    )
    if chosen is None:
        raise CliError("cancelled", code="cancelled")
    return str(chosen)


def _add(client, account_id: str, args: object, ui: Ui) -> int:
    kind = getattr(args, "kind", None)
    if not kind:
        if not ui.interactive:
            raise CliError(
                "choose --kind smtp or --kind gmail_api",
                code="usage",
                exit_code=2,
            )
        kind = prompts.choose("Send mechanism", KINDS, ui=ui, back=False)
        if kind is None:
            raise CliError("cancelled", code="cancelled")
    concurrency = getattr(args, "max_concurrency", None)
    rate = getattr(args, "rate_per_min", None)
    if kind == "gmail_api":
        if concurrency is None:
            concurrency = _ask_int("Parallel API sends", ui, default=2)
        if rate is None and ui.interactive:
            rate = _ask_optional_int("API calls per minute", ui)
    body = {
        "kind": kind,
        "priority": getattr(args, "priority", 0),
        "max_concurrency": concurrency or 1,
        "rate_per_min": rate,
        "oauth_client_id": getattr(args, "oauth_client", None),
    }
    binding = post(client, f"/api/accounts/{account_id}/transports", body)
    return _show_binding(binding, ui, "added")


def _set(client, account_id: str, args: object, ui: Ui) -> int:
    binding_id = getattr(args, "binding_id", None)
    if not binding_id:
        if not ui.interactive:
            raise CliError(
                "transport set needs a binding id",
                code="usage",
                exit_code=2,
            )
        binding_id = _choose_binding(client, account_id, ui, "change")
    changes: dict[str, object] = {}
    priority = getattr(args, "priority", None)
    concurrency = getattr(args, "max_concurrency", None)
    rate = getattr(args, "rate_per_min", None)
    enabled = getattr(args, "enabled", None)
    if priority is not None:
        changes["priority"] = priority
    if concurrency is not None:
        changes["max_concurrency"] = concurrency
    if rate is not None:
        changes["rate_per_min"] = rate
    if enabled is not None:
        changes["enabled"] = enabled
    if not changes:
        if not ui.interactive:
            raise CliError(
                "transport set needs at least one change",
                code="usage",
                exit_code=2,
            )
        changes = _ask_changes(client, account_id, binding_id, ui)
    binding = patch(
        client, f"/api/accounts/{account_id}/transports/{binding_id}", changes
    )
    return _show_binding(binding, ui, "updated")


def _ask_changes(client, account_id: str, binding_id: str, ui: Ui) -> dict:
    current = get(client, f"/api/accounts/{account_id}/transports/{binding_id}")
    field = prompts.choose("What to change", FIELDS, ui=ui, back=False)
    if field is None:
        raise CliError("cancelled", code="cancelled")
    if field == "priority":
        return {"priority": _ask_int("Priority", ui, current["priority"])}
    if field == "max_concurrency":
        return {
            "max_concurrency": _ask_int(
                "Parallel sends", ui, current["max_concurrency"]
            )
        }
    if field == "rate_per_min":
        return {"rate_per_min": _ask_optional_int("API calls per minute", ui)}
    return {
        "enabled": prompts.confirm(
            "enable the transport?", ui=ui, default=current["enabled"]
        )
    }


def _remove(client, account_id: str, args: object, ui: Ui) -> int:
    binding_id = getattr(args, "binding_id", None)
    if not binding_id:
        if not ui.interactive:
            raise CliError(
                "transport remove needs a binding id",
                code="usage",
                exit_code=2,
            )
        binding_id = _choose_binding(client, account_id, ui, "remove")
    prompts.confirm(
        f"remove transport {binding_id}?",
        ui=ui,
        yes_flag=bool(getattr(args, "yes", False)),
    )
    binding = delete(
        client,
        f"/api/accounts/{account_id}/transports/{binding_id}",
        confirm="true",
    )
    if ui.json_mode:
        json_out(binding)
        return 0
    record({"transport": f"{binding['id']} {binding['kind']} removed"})
    return 0


def _test(client, account_id: str, args: object, ui: Ui) -> int:
    binding_id = getattr(args, "binding_id", None)
    if not binding_id:
        if not ui.interactive:
            raise CliError(
                "transport test needs a binding id",
                code="usage",
                exit_code=2,
            )
        binding_id = _choose_binding(client, account_id, ui, "test")
    try:
        result = post(
            client, f"/api/accounts/{account_id}/transports/{binding_id}/test"
        )
    except CliError as error:
        if error.code == "daemon_timeout":
            budget = float(getattr(client, "budget", 0) or 0)
            raise CliError(
                f"the transport probe was still running after {budget:.0f}s",
                code="transport_test_timeout",
                hint="retry with --timeout 120, then read `downcroc logs --event transport`",
            ) from error
        raise
    if ui.json_mode:
        json_out(result)
        return 0
    fields = {
        "transport": binding_id,
        "result": "connected" if result["ok"] else "failed",
        "health": result["health"],
    }
    if not result["ok"] and result.get("code"):
        fields["code"] = result["code"]
    fields["reason"] = result["message"]
    record(fields)
    return 0


def _show_binding(binding: dict, ui: Ui, verb: str) -> int:
    if ui.json_mode:
        json_out(binding)
        return 0
    record(
        {
            "transport": f"{binding['id']} {binding['kind']} {verb}",
            "priority": binding["priority"],
            "lanes": binding["max_concurrency"],
            "rate_per_min": binding["rate_per_min"] or "-",
            "health": binding["health"],
        }
    )
    return 0


def _ask_int(label: str, ui: Ui, default: int) -> int:
    answer = prompts.ask(label, ui=ui, default=str(default))
    try:
        return int(answer)
    except ValueError as error:
        raise CliError(
            f"{label} must be a whole number", code="input_invalid"
        ) from error


def _ask_optional_int(label: str, ui: Ui) -> int | None:
    answer = prompts.ask(label, ui=ui, required=False)
    if not answer.strip():
        return None
    try:
        return int(answer)
    except ValueError as error:
        raise CliError(
            f"{label} must be a whole number", code="input_invalid"
        ) from error

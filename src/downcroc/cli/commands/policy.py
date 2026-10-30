from __future__ import annotations

from downcroc.cli.client import api, delete, get, put
from downcroc.cli.context import load
from downcroc.cli.errors import CliError
from downcroc.cli.output import json_out, table
from downcroc.cli.ui.session import Ui

FIELDS = (
    "daily_allowance",
    "window_start",
    "window_end",
    "jitter_min",
    "jitter_max",
    "max_in_flight",
    "enabled",
)


def _payload(args: object) -> dict:
    values = {
        field: getattr(args, field, None)
        for field in FIELDS
        if getattr(args, field, None) is not None
    }
    if getattr(args, "for_s", None) is not None:
        values["for_s"] = args.for_s
    return values


def _render(view: dict, ui: Ui) -> None:
    if ui.json_mode:
        json_out(view)
        return
    table(
        ["field", "value", "source"],
        [
            [field, view["values"][field], view["sources"].get(field, "default")]
            for field in FIELDS
        ],
    )
    if view.get("temporary"):
        print()
        print("temporary override:")
        table(
            ["field", "value"],
            [[key, value] for key, value in view["temporary"].items()],
        )
        if view.get("expires_at"):
            print(f"expires {view['expires_at']}")
    if view.get("permanent"):
        print()
        print("account override:")
        table(
            ["field", "value"],
            [[key, value] for key, value in view["permanent"].items()],
        )


def account_policy(client, args: object, ui: Ui) -> int:
    action = getattr(args, "policy_action", None) or "show"
    account_id = args.account_id
    if action == "show":
        view = get(client, f"/api/accounts/{account_id}/policy")
        _render(view, ui)
        return 0
    if action == "clear":
        view = delete(client, f"/api/accounts/{account_id}/policy")
        _render(view, ui)
        return 0
    if action == "clear-temporary":
        view = delete(client, f"/api/accounts/{account_id}/policy/temporary")
        _render(view, ui)
        return 0
    if action != "set":
        raise CliError(f"unknown policy action: {action}", code="usage", exit_code=2)
    payload = _payload(args)
    if not payload:
        raise CliError(
            "nothing to set",
            code="usage",
            hint="pass a field like --daily-allowance or --off",
            exit_code=2,
        )
    view = put(client, f"/api/accounts/{account_id}/policy", payload)
    _render(view, ui)
    return 0


def sending(args: object, ui: Ui) -> int:
    action = getattr(args, "action", None) or "show"
    paths, _, _ = load()
    with api(paths) as client:
        if action == "show":
            _render(get(client, "/api/sending"), ui)
            return 0
        if action == "clear":
            _render(delete(client, "/api/sending"), ui)
            return 0
        if action != "set":
            raise CliError(
                f"unknown sending action: {action}", code="usage", exit_code=2
            )
        payload = _payload(args)
        if not payload:
            raise CliError(
                "nothing to set",
                code="usage",
                hint="pass a field like --daily-allowance or --off",
                exit_code=2,
            )
        _render(put(client, "/api/sending", payload), ui)
        return 0

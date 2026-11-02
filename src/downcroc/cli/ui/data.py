from __future__ import annotations

from collections.abc import Callable

from downcroc.cli.client import api, get, get_page
from downcroc.cli.context import load
from downcroc.cli.errors import CliError, render
from downcroc.cli.ui.menu import Item, run_args
from downcroc.cli.ui.session import Ui

LIMIT = 50


def rows(
    ui: Ui,
    path: str,
    **params: object,
) -> list[dict] | None:
    paths, _, _ = load()
    try:
        with api(paths) as client:
            found, _total = get_page(client, path, limit=LIMIT, **params)
    except CliError as error:
        render(error, json_mode=ui.json_mode)
        return None
    return found


def action(ui: Ui, *argv: str) -> Callable[[], object]:
    return lambda: run_args(ui, *argv)


def one(ui: Ui, path: str, **params: object) -> dict | None:
    paths, _, _ = load()
    try:
        with api(paths) as client:
            return get(client, path, **params)
    except CliError as error:
        render(error, json_mode=ui.json_mode)
        return None


def need_daemon(ui: Ui) -> list[Item]:
    return [
        Item(
            "The daemon is not running",
            detail="start it to load this list",
            action=action(ui, "service", "start"),
        )
    ]

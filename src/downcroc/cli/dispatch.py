from __future__ import annotations

import importlib
from collections.abc import Callable

from downcroc.cli.parser import build_parser

Handler = Callable[[object], int]

HANDLERS: dict[str, str] = {
    "init": "downcroc.cli.commands.init:run",
    "help": "downcroc.cli.commands.help:run",
    "status": "downcroc.cli.commands.state:run",
    "doctor": "downcroc.cli.commands.state:run",
    "send": "downcroc.cli.commands.send:run",
    "review": "downcroc.cli.commands.review:run",
    "docs": "downcroc.cli.commands.docs:run",
    "service": "downcroc.cli.commands.service:run",
    "openapi": "downcroc.cli.commands.openapi:run",
    "backup": "downcroc.cli.commands.backup:run",
    "restore": "downcroc.cli.commands.restore:run",
    "auth": "downcroc.cli.commands.auth:run",
    "vault": "downcroc.cli.commands.vault:run",
    "provider": "downcroc.cli.commands.providers:run",
    "account": "downcroc.cli.commands.accounts:run",
    "batch": "downcroc.cli.commands.batches:run",
    "template": "downcroc.cli.commands.templates:run",
    "job": "downcroc.cli.commands.jobs:run",
    "failed": "downcroc.cli.commands.failed:run",
    "config": "downcroc.cli.commands.config:run",
    "sending": "downcroc.cli.commands.sending:run",
    "stats": "downcroc.cli.commands.stats:run",
    "mail": "downcroc.cli.commands.mail:run",
    "logs": "downcroc.cli.commands.logs:run",
    "update": "downcroc.cli.commands.update:run",
    "uninstall": "downcroc.cli.commands.uninstall:run",
}


def _handler(command: str) -> Handler | None:
    target = HANDLERS.get(command)
    if target is None:
        return None
    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attribute, None)


def dispatch(args: object) -> int:
    command = getattr(args, "command", None)
    if command == "serve":
        from downcroc.cli.commands import serve

        serve.run()
        return 0
    if command is None:
        from downcroc.cli.commands import state

        return state.run(args)
    handler = _handler(command)
    if handler is None:
        raise KeyError(command)
    return handler(args)


def configure(args: object) -> None:
    from downcroc.cli import output

    output.configure(
        wide=bool(getattr(args, "wide", False)),
        full=bool(getattr(args, "full", False)),
    )


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    configure(args)
    return dispatch(args)

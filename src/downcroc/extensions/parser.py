from __future__ import annotations

import argparse

from downcroc.cli.parser.common import common


def add_extensions(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "extension",
        help="manage extensions",
        description="Manage installed extensions and their capability grants.",
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list extensions")
    common(listing)
    listing.set_defaults(action="list")
    show = actions.add_parser("show", help="show one extension")
    show.add_argument("extension")
    common(show)
    show.set_defaults(action="show")

    add = actions.add_parser("add", help="install a manifest")
    add.add_argument("path")
    add.set_defaults(action="add")

    enable = actions.add_parser("enable", help="enable an extension")
    enable.add_argument("extension")
    enable.set_defaults(action="enable")

    disable = actions.add_parser("disable", help="disable an extension")
    disable.add_argument("extension")
    disable.set_defaults(action="disable")

    actions.add_parser("reload", help="reload manifests").set_defaults(action="reload")

    logs = actions.add_parser("logs", help="show extension event logs")
    logs.add_argument("extension")
    logs.add_argument("--follow", action="store_true")
    common(logs)
    logs.set_defaults(action="logs")

    capabilities = actions.add_parser("capabilities", help="list capabilities")
    common(capabilities)
    capabilities.set_defaults(action="capabilities")

    test = actions.add_parser("test", help="run an extension once")
    test.add_argument("extension")
    test.add_argument("--input", required=True, help="JSON event payload")
    common(test)

    run = actions.add_parser("run", help="run a registered command")
    run.add_argument("extension")
    run.add_argument("command")
    run.add_argument("args", nargs="*")
    common(run)

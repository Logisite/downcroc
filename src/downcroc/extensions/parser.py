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

    add = actions.add_parser("add", help="install a manifest or artifact")
    add.add_argument("path")
    common(add)
    add.set_defaults(action="add")

    build = actions.add_parser("build", help="build a single-file artifact")
    build.add_argument("directory")
    build.add_argument("--output")
    common(build)
    build.set_defaults(action="build")

    verify = actions.add_parser("verify", help="verify an installed artifact")
    verify.add_argument("extension")
    common(verify)
    verify.set_defaults(action="verify")

    approval = actions.add_parser("approval", help="show approval status")
    approval.add_argument("extension")
    common(approval)
    approval.set_defaults(action="approval")

    approve = actions.add_parser("approve", help="approve elevated capabilities")
    approve.add_argument("extension")
    approve.add_argument("--password", help="vault password, prompts if omitted")
    common(approve)
    approve.set_defaults(action="approve")

    inject = actions.add_parser("inject", help="inject an event for testing")
    inject.add_argument("extension")
    inject.add_argument("--event", required=True)
    inject.add_argument("--payload", default="{}", help="JSON event payload")
    common(inject)
    inject.set_defaults(action="inject")

    revoke = actions.add_parser("revoke", help="revoke elevated capabilities")
    revoke.add_argument("extension")
    common(revoke)
    revoke.set_defaults(action="revoke")

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
    test.add_argument("--rounds", type=int, default=1, help="action rounds to run")
    common(test)

    run = actions.add_parser("run", help="run a registered command")
    run.add_argument("extension")
    run.add_argument("command")
    run.add_argument("args", nargs="*")
    common(run)

from __future__ import annotations

import argparse

from downcroc.cli.parser.common import common


def vault(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "vault",
        help="create, inspect, and unlock the credential vault",
        epilog=(
            "examples:\n"
            "  downcroc vault init\n"
            "  downcroc vault unlock --password-file /run/secrets/downcroc\n"
            "  downcroc vault keyring status"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    status = actions.add_parser("status", help="show the vault state")
    common(status)

    init = actions.add_parser("init", help="create the vault")
    _password_options(init)
    common(init)

    unlock = actions.add_parser("unlock", help="unlock the vault")
    _password_options(unlock)
    common(unlock)

    lock = actions.add_parser("lock", help="lock the vault")
    lock.add_argument(
        "--forget",
        action="store_true",
        help="also delete the stored master password",
    )
    common(lock)

    keyring = actions.add_parser("keyring", help="control the credential store")
    keyring.add_argument(
        "action",
        choices=["status", "enable", "disable"],
        help="show, turn on, or turn off the store",
    )
    _password_options(keyring)
    common(keyring)


def _password_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin",
    )
    parser.add_argument(
        "--password-file",
        metavar="PATH",
        help="read the password from a 0600 file",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--keyring",
        action="store_true",
        help="use the system credential store",
    )
    group.add_argument(
        "--no-keyring",
        action="store_true",
        help="do not read or write the credential store",
    )

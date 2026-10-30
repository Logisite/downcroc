from __future__ import annotations

import argparse

from downcroc.cli.parser import account, batch, other, provider
from downcroc.cli.parser.common import Parser, root
from downcroc.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="downcroc",
        description="local email orchestration daemon",
        epilog=(
            "examples:\n"
            "  downcroc init\n"
            "  downcroc send campaign.json\n"
            "  downcroc help vault"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"downcroc {__version__}"
    )
    root(parser)
    commands = parser.add_subparsers(dest="command", metavar="command")

    other.top(commands)
    account.service(commands)
    account.attach_auth(commands)
    account.vault(commands)
    provider.provider(commands)
    account.account(commands)
    batch.batch(commands)
    batch.template(commands)
    batch.job(commands)
    batch.failed(commands)
    other.config(commands)
    other.sending(commands)
    other.stats(commands)
    other.mail(commands)
    other.logs(commands)
    other.files(commands)
    return parser

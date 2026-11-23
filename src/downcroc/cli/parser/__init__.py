from __future__ import annotations

import argparse

from downcroc.cli.parser import account, batch, other, provider, vault
from downcroc.cli.parser.common import Parser, common, root
from downcroc.extensions.manifest import load_manifests
from downcroc.extensions.parser import add_extensions
from downcroc.runtime.paths import resolve


class VersionAction(argparse.Action):
    """Load the package version only when --version is actually used."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        from downcroc.version import __version__

        print(f"downcroc {__version__}")
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="downcroc",
        description="local email orchestration daemon",
        epilog=(
            "examples:\n"
            "  downcroc init\n"
            "  downcroc send campaign.json\n"
            "  downcroc help vault\n"
            "\n"
            "this help can lag behind the release; the docs are kept current:\n"
            "  downcroc docs"
        ),
    )
    parser.add_argument("--version", action=VersionAction, nargs=0)
    root(parser)
    commands = parser.add_subparsers(dest="command", metavar="command")

    other.top(commands)
    account.service(commands)
    account.attach_auth(commands)
    vault.vault(commands)
    provider.provider(commands)
    account.account(commands)
    batch.batch(commands)
    batch.template(commands)
    batch.job(commands)
    batch.failed(commands)
    other.config(commands)
    other.sending(commands)
    other.stats(commands)
    other.backfill(commands)
    other.followups(commands)
    other.mail(commands)
    other.logs(commands)
    other.files(commands)
    add_extensions(commands)
    _add_extension_commands(commands)
    return parser


def _add_extension_commands(commands: argparse._SubParsersAction) -> None:
    paths = resolve()
    manifests = load_manifests(paths.config / "extensions")
    for manifest in manifests:
        for command in manifest.commands:
            name = command.name
            if name in commands._name_parser_map:
                continue
            parser = commands.add_parser(name, help=command.help)
            parser.set_defaults(
                action="run",
                extension_id=manifest.id,
                extension_command=name,
            )
            for arg in command.args:
                parser.add_argument(f"--{arg}")
            common(parser)

from __future__ import annotations

import sys

from downcroc.cli.parser import build_parser
from downcroc.cli.ui import help as topics
from downcroc.cli.ui.session import Ui, build


def overview(ui: Ui) -> str:
    parser = build_parser()
    return parser.format_help().rstrip() + "\n\n" + topics.index(ui)


def show(topic: str, ui: Ui) -> int:
    text = topics.render(topic, ui)
    if text is not None:
        sys.stdout.write(text)
        return 0
    parser = build_parser()
    choices = _commands(parser)
    if topic in choices:
        try:
            parser.parse_args([topic, "--help"])
        except SystemExit as stop:
            return int(stop.code or 0)
        return 0
    sys.stderr.write(topics.index(ui))
    return 2


def _commands(parser) -> dict:
    groups = getattr(parser, "_subparsers", None)
    if groups is None:
        return {}
    return dict(groups._group_actions[0].choices)


def run(args: object) -> int:
    ui = build(args)
    topic = getattr(args, "topic", None)
    if not topic:
        sys.stdout.write(overview(ui))
        return 0
    return show(topic, ui)

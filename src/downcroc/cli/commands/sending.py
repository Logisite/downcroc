from __future__ import annotations

from downcroc.cli.commands.policy import sending
from downcroc.cli.ui.session import build


def run(args: object) -> int:
    return sending(args, build(args))

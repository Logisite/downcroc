from __future__ import annotations

from downcroc.cli import dispatch
from downcroc.cli.errors import Cancelled, CliError
from downcroc.cli.ui.tree.argv import compose, missing
from downcroc.cli.ui.tree.spec import CommandSpec
from downcroc.cli.ui.tree.state import Globals, LeafState


def execute(
    spec: CommandSpec,
    state: LeafState,
    globals: Globals,
) -> tuple[int, str, list[str], str | None]:
    gaps = missing(spec, state)
    if gaps:
        return (
            2,
            f"{gaps[0].arg.label()} is required",
            compose(spec, state, globals),
            None,
        )
    argv = compose(spec, state, globals)
    try:
        return dispatch.run(argv), "", argv, None
    except CliError as error:
        return error.exit_code, error.label, argv, error.code
    except Cancelled:
        return 130, "cancelled", argv, None
    except KeyboardInterrupt:
        return 130, "interrupted", argv, None

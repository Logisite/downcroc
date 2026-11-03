from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from downcroc.cli.errors import Cancelled, CliError, UsageError, render

if TYPE_CHECKING:
    from downcroc.runtime.config.loader import ConfigError


def _config_error(error: ConfigError) -> CliError:
    detail = f"{error.field}: {error}" if error.field else str(error)
    return CliError(
        detail,
        code="config_invalid",
        hint="run downcroc config show",
    )


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] in {"--version", "-V"}:
        from downcroc.version import __version__

        print(f"downcroc {__version__}")
        return 0
    from downcroc.cli import dispatch
    from downcroc.cli.parser import build_parser

    parser = build_parser()
    try:
        args = parser.parse_args(values)
    except UsageError as error:
        render(error)
        return error.exit_code
    except SystemExit as stop:
        return int(stop.code or 0)
    dispatch.configure(args)

    try:
        return dispatch.dispatch(args)
    except Cancelled:
        print("cancelled", file=sys.stderr)
        return 130
    except CliError as error:
        render(error, json_mode=bool(getattr(args, "json", False)))
        return error.exit_code
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 1
    except OSError as error:
        render(CliError(str(error), code="io_error"))
        return 1
    except Exception as error:
        from downcroc.runtime.config.loader import ConfigError

        if not isinstance(error, ConfigError):
            raise
        render(_config_error(error), json_mode=bool(getattr(args, "json", False)))
        return 1


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import re
from datetime import date

from downcroc.cli.errors import UsageError
from downcroc.domain.batches import BatchState
from downcroc.domain.jobs import JobState

BATCH_STATES = [state.value for state in BatchState]
JOB_STATES = [state.value for state in JobState]
LEVELS = ["debug", "info", "warning", "error"]
GLYPHS = ["auto", "nerd", "ascii"]
COLOURS = ["auto", "always", "never"]


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise UsageError(message, hint=f"{self.prog} -h")


def positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    if number > 500:
        raise argparse.ArgumentTypeError("must be at most 500")
    return number


def non_negative(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def day(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from error
    return value


def duration(value: str) -> int:
    match = re.fullmatch(r"(\d+)([smhd])", value.strip().lower())
    if match is None:
        raise argparse.ArgumentTypeError("use a duration like 30s, 15m, 2h, or 7d")
    amount = int(match.group(1))
    if amount < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    unit = match.group(2)
    seconds = amount * {"s": 1, "m": 60, "h": 3_600, "d": 86_400}[unit]
    if seconds > 2_592_000:
        raise argparse.ArgumentTypeError("must be 30 days or less")
    return seconds


def policy_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--daily-allowance", type=positive)
    parser.add_argument("--window-start", type=non_negative)
    parser.add_argument("--window-end", type=non_negative)
    parser.add_argument("--jitter-min", type=non_negative)
    parser.add_argument("--jitter-max", type=non_negative)
    parser.add_argument("--max-in-flight", type=positive)
    state = parser.add_mutually_exclusive_group()
    state.add_argument("--on", action="store_true", dest="enabled")
    state.add_argument("--off", action="store_false", dest="enabled")
    parser.set_defaults(enabled=None)
    parser.add_argument(
        "--for",
        dest="for_s",
        type=duration,
        metavar="DURATION",
        help="set a temporary override, for example 2h or 7d",
    )


def common(
    parser: argparse.ArgumentParser, *, yes: bool = False, timeout: bool = True
) -> None:
    suppress = argparse.SUPPRESS
    parser.add_argument(
        "--json",
        action="store_true",
        default=suppress,
        help="print machine-readable JSON",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        default=suppress,
        help="fail instead of prompting",
    )
    if yes:
        parser.add_argument(
            "--yes",
            action="store_true",
            default=suppress,
            help="skip the confirmation prompt",
        )
    parser.add_argument(
        "--wide",
        action="store_true",
        default=suppress,
        help="use the full terminal width",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=suppress,
        help="do not truncate values",
    )
    parser.add_argument(
        "--glyphs",
        choices=GLYPHS,
        default=suppress,
        help="glyph set: auto follows cli.glyphs",
    )
    parser.add_argument(
        "--color",
        choices=COLOURS,
        default=suppress,
        help="colour output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=suppress,
        help="suppress next-step lines",
    )
    if timeout:
        parser.add_argument(
            "--timeout",
            type=float,
            default=suppress,
            help="daemon request timeout in seconds",
        )
    parser.add_argument(
        "--no-pager",
        action="store_true",
        default=suppress,
        help="never page long output",
    )


def root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="fail instead of prompting",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="consent for a named destructive action",
    )
    parser.add_argument(
        "--wide",
        action="store_true",
        help="use the full terminal width",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="do not truncate values",
    )
    parser.add_argument("--glyphs", choices=GLYPHS, default="auto", help="glyph set")
    parser.add_argument(
        "--color", choices=COLOURS, default="auto", help="colour output"
    )
    parser.add_argument("--quiet", action="store_true", help="suppress next-step lines")
    parser.add_argument(
        "--timeout", type=float, default=None, help="daemon request timeout"
    )
    parser.add_argument(
        "--no-pager", action="store_true", help="never page long output"
    )


def limit(parser: argparse.ArgumentParser, default: int = 100) -> None:
    parser.add_argument(
        "--limit",
        type=positive,
        default=default,
        help=f"maximum rows to return (1-500, default {default})",
    )
    parser.add_argument(
        "--offset",
        type=non_negative,
        default=0,
        help="rows to skip",
    )

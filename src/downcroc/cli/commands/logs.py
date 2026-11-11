from __future__ import annotations

import json
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType

from downcroc.cli.context import load
from downcroc.cli.errors import CliError, UsageError, render
from downcroc.cli.logs_addresses import AddressBook
from downcroc.cli.output import colour_enabled
from downcroc.cli.ui.session import Ui, build
from downcroc.runtime.logging.format import render as render_entry
from downcroc.runtime.paths import Paths
from downcroc.runtime.service.lock import running

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
ACCEPTED = "15m, 2h, 3d, or an ISO 8601 timestamp"


def parse_since(text: str) -> datetime:
    if len(text) > 1 and text[-1] in UNITS and text[:-1].isdigit():
        return datetime.now(tz=UTC) - timedelta(
            seconds=int(text[:-1]) * UNITS[text[-1]]
        )
    return datetime.fromisoformat(text)


def oldest_first(paths: Paths) -> list[Path]:
    base = paths.log_file
    rotated = [
        path for path in base.parent.glob(f"{base.name}.*") if path.suffix[1:].isdigit()
    ]
    rotated.sort(key=lambda path: int(path.suffix[1:]), reverse=True)
    if base.exists():
        rotated.append(base)
    return rotated


def matches(entry: dict, args: object, cutoff: datetime | None) -> bool:
    if args.event and not str(entry.get("event", "")).startswith(args.event):
        return False
    if args.level and entry.get("level") != args.level:
        return False
    for name in ("account", "batch", "job"):
        wanted = getattr(args, name, None)
        if wanted and str(entry.get(name, "")) != wanted:
            return False
    if cutoff is not None:
        stamp = str(entry.get("ts", ""))
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return False
        if moment < cutoff:
            return False
    return True


def _print(entry: dict, raw: bool, book: AddressBook, addresses: bool) -> None:
    if addresses:
        entry = book.apply(entry, json_mode=raw)
    if raw:
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    else:
        print(render_entry(entry, colour=colour_enabled()), flush=True)


def _entries(path: Path) -> list[dict]:
    found = []
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                found.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return found


def _missing(paths: Paths, ui: Ui) -> int:
    error = CliError(
        f"no log file at {paths.log_file}",
        code="no_log_file",
        fields={"path": str(paths.log_file)},
    )
    if running(paths.service_file) is None:
        error.hint = "start the daemon with: downcroc service start"
    if ui.json_mode:
        render(error, json_mode=True)
    else:
        print(error.message, file=sys.stderr)
        if error.hint:
            print(f"  hint: {error.hint}", file=sys.stderr)
    return 1


def _cutoff(args: object) -> datetime | None:
    if not args.since:
        return None
    try:
        return parse_since(args.since)
    except ValueError as error:
        raise UsageError(
            f"--since must be {ACCEPTED}",
            hint="downcroc logs -h",
        ) from error


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    cutoff = _cutoff(args)
    if not paths.log_file.exists():
        return _missing(paths, ui)
    book = AddressBook(paths)
    if args.addresses:
        book.refresh()
        args.account = book.filter(args.account)
    if args.follow:
        return _follow(paths, args, cutoff, ui, book)

    found: list[dict] = []
    for path in oldest_first(paths):
        found.extend(entry for entry in _entries(path) if matches(entry, args, cutoff))
    shown = found[-args.limit :]
    for entry in shown:
        _print(entry, ui.json_mode, book, args.addresses)
    if not found:
        print("no events match", file=sys.stderr)
    elif len(found) > len(shown) and not ui.json_mode:
        print(
            f"showing {len(shown)} of {len(found)}, use --since or --limit",
            file=sys.stderr,
        )
    return 0


def _follow(
    paths: Paths,
    args: object,
    cutoff: datetime | None,
    ui: Ui,
    book: AddressBook,
) -> int:
    found: list[dict] = []
    for path in oldest_first(paths):
        found.extend(entry for entry in _entries(path) if matches(entry, args, cutoff))
    shown = found[-args.limit :]
    for entry in shown:
        _print(entry, ui.json_mode, book, args.addresses)
    if len(found) > len(shown) and not ui.json_mode:
        print(
            f"showing {len(shown)} of {len(found)}, use --since or --limit",
            file=sys.stderr,
        )

    stop = False

    def halt(signum: int, frame: FrameType | None) -> None:
        nonlocal stop
        stop = True

    previous = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, halt)
    except ValueError:
        pass

    inode = None
    handle = None
    try:
        while not stop:
            if not paths.log_file.exists():
                time.sleep(0.2)
                continue
            stat = paths.log_file.stat()
            if stat.st_ino != inode:
                if handle is not None:
                    handle.close()
                fresh = inode is None
                inode = stat.st_ino
                handle = paths.log_file.open(encoding="utf-8", errors="replace")
                if fresh:
                    handle.seek(0, 2)
                elif not ui.json_mode:
                    print(
                        f"log rotated, following {paths.log_file}",
                        file=sys.stderr,
                    )
            line = handle.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(entry.get("event", "")).startswith("account."):
                book.refresh()
            if matches(entry, args, cutoff):
                _print(entry, ui.json_mode, book, args.addresses)
    except KeyboardInterrupt:
        return 0
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if handle is not None:
            handle.close()
    return 0

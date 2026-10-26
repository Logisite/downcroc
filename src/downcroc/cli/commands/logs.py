from __future__ import annotations

import json
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType

from downcroc.cli.output import colour_enabled
from downcroc.runtime.logging.format import render
from downcroc.runtime.paths import Paths, resolve

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


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


def _print(entry: dict, raw: bool) -> None:
    if raw:
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    else:
        print(render(entry, colour=colour_enabled()), flush=True)


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


def run(args: object) -> int:
    paths = resolve()
    try:
        cutoff = parse_since(args.since) if args.since else None
    except ValueError:
        print(f"cannot read --since {args.since}", file=sys.stderr)
        return 1

    if args.follow:
        return _follow(paths, args, cutoff)

    found: list[dict] = []
    for path in oldest_first(paths):
        found.extend(entry for entry in _entries(path) if matches(entry, args, cutoff))
    for entry in found[-args.limit :]:
        _print(entry, args.json)
    return 0


def _follow(paths: Paths, args: object, cutoff: datetime | None) -> int:
    found: list[dict] = []
    for path in oldest_first(paths):
        found.extend(entry for entry in _entries(path) if matches(entry, args, cutoff))
    for entry in found[-args.limit :]:
        _print(entry, args.json)

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
            line = handle.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if matches(entry, args, cutoff):
                _print(entry, args.json)
    except KeyboardInterrupt:
        return 0
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if handle is not None:
            handle.close()
    return 0

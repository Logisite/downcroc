from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from downcroc.runtime.logging import context

RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
    }
)

LEVELS = {"debug", "info", "warning", "error", "critical"}
DIM = "\x1b[2m"
BOLD = "\x1b[1m"
RESET = "\x1b[0m"
LEVEL_COLOUR = {
    "debug": "\x1b[2m",
    "info": "\x1b[36m",
    "warning": "\x1b[33m",
    "error": "\x1b[31m",
    "critical": "\x1b[1;31m",
}


def entry_from(record: logging.LogRecord) -> dict[str, Any]:
    moment = datetime.fromtimestamp(record.created, tz=UTC)
    entry: dict[str, Any] = {
        "ts": moment.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": record.levelname.lower(),
        "event": record.getMessage(),
        "logger": record.name,
    }
    entry.update(context.current())
    for key, value in record.__dict__.items():
        if key in RESERVED or key in entry or key == "color_message":
            continue
        field = key.removeprefix("meta_")
        if field != key and field in entry:
            entry[key] = value
            continue
        entry[field] = value
    if record.exc_info:
        entry["error"] = "".join(traceback.format_exception(*record.exc_info)).strip()
    return entry


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(entry_from(record), default=str, ensure_ascii=False)


def render(entry: dict[str, Any], colour: bool = True) -> str:
    stamp = str(entry.get("ts", ""))[11:23]
    level = str(entry.get("level", "info"))
    event = str(entry.get("event", ""))
    fields = "  ".join(
        f"{key}={value}"
        for key, value in entry.items()
        if key not in {"ts", "level", "logger"} and key != "event"
    )
    if colour:
        tint = LEVEL_COLOUR.get(level, "")
        head = f"{DIM}{stamp}{RESET}  {tint}{level:<7}{RESET}  {BOLD}{event:<24}{RESET}"
        pairs = f"  {DIM}{fields}{RESET}" if fields else ""
        return (head + pairs).rstrip()
    return f"{stamp}  {level:<7}  {event:<24}  {fields}".rstrip()


class PrettyFormatter(logging.Formatter):
    def __init__(self, colour: bool = True) -> None:
        super().__init__()
        self.colour = colour

    def format(self, record: logging.LogRecord) -> str:
        return render(entry_from(record), colour=self.colour)

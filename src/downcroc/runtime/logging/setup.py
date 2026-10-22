from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from typing import Any, TextIO

from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.format import RESERVED, JsonFormatter, PrettyFormatter
from downcroc.runtime.paths import Paths, ensure

SENSITIVE = (
    "password",
    "passphrase",
    "secret",
    "token",
    "authorization",
    "credential",
    "api_key",
)


class PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def _open(self) -> Any:
        stream = super()._open()
        os.chmod(self.baseFilename, 0o600)
        return stream


class Redaction(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in list(record.__dict__.items()):
            if isinstance(value, str) and any(
                word in key.lower() for word in SENSITIVE
            ):
                record.__dict__[key] = "***"
        return True


class EventLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _emit(self, level: int, event: str, **fields: Any) -> None:
        safe = {
            f"meta_{key}" if key in RESERVED else key: value
            for key, value in fields.items()
        }
        self._logger.log(level, event, extra=safe)

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, **fields)


def setup_logging(
    paths: Paths,
    settings: Settings,
    stream: TextIO | None = None,
) -> EventLogger:
    ensure(paths)
    level = getattr(logging, settings.logging.level.upper())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    paths.log_file.touch(mode=0o600, exist_ok=True)
    paths.log_file.chmod(0o600)
    rotating = PrivateRotatingFileHandler(
        paths.log_file,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backups,
        encoding="utf-8",
    )
    rotating.setFormatter(JsonFormatter())
    rotating.addFilter(Redaction())
    root.addHandler(rotating)

    if stream is not None:
        pretty = logging.StreamHandler(stream)
        pretty.setFormatter(PrettyFormatter(colour=stream.isatty()))
        pretty.addFilter(Redaction())
        root.addHandler(pretty)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return EventLogger(root)


def console(settings: Settings | None = None) -> EventLogger:
    stream = sys.stderr if sys.stderr.isatty() else None
    level = logging.INFO
    if settings is not None:
        level = getattr(logging, settings.logging.level.upper())
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(PrettyFormatter(colour=sys.stderr.isatty()))
        handler.addFilter(Redaction())
        root.addHandler(handler)
    root.setLevel(level)
    return EventLogger(root)

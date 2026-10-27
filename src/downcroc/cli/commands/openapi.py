from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from downcroc.api.app import create_app
from downcroc.cli import paths as path_tools
from downcroc.cli.errors import CliError
from downcroc.runtime.config.loader import ConfigError, read
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger, setup_logging
from downcroc.runtime.paths import Paths, resolve


def _settings(paths: Paths) -> Settings:
    if not paths.config_file.exists():
        return Settings()
    try:
        return read(paths.config_file)
    except ConfigError:
        return Settings()


def _document(paths: Paths, settings: Settings, log: EventLogger) -> dict[str, Any]:
    app = create_app(settings, paths, log)
    return app.openapi()


def _destination(output: str | None, *, mkdir: bool) -> Path | None:
    if output is None or output == "-":
        return None
    target = path_tools.expand(output)
    if target.exists() and target.is_dir():
        raise CliError(
            "the output path is a directory",
            code="input_invalid",
            fields={"path": str(target)},
            hint="pass a file name",
        )
    if not target.parent.is_dir():
        if not mkdir:
            raise CliError(
                "the parent directory does not exist",
                code="input_invalid",
                fields={"path": str(target.parent)},
                hint="create it first, or pass --mkdir",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def run(args: object) -> int:
    paths = resolve()
    settings = _settings(paths)
    log = setup_logging(paths, settings)
    document = _document(paths, settings, log)
    text = json.dumps(document, indent=2) + "\n"
    target = _destination(getattr(args, "output", None), mkdir=bool(args.mkdir))
    if target is None:
        sys.stdout.write(text)
        destination = "stdout"
    else:
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")
        destination = str(target)
    log.info(
        "openapi.exported",
        path=destination,
        routes=len(document.get("paths", {})),
    )
    return 0

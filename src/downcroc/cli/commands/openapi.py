from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from downcroc.api.app import create_app
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


def run(output: Path | None) -> int:
    paths = resolve()
    settings = _settings(paths)
    log = setup_logging(paths, settings)
    document = _document(paths, settings, log)
    text = json.dumps(document, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        destination = "stdout"
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"wrote {output}")
        destination = str(output)
    log.info(
        "openapi.exported",
        path=destination,
        routes=len(document.get("paths", {})),
    )
    return 0

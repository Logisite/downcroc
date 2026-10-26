from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from downcroc.api.app import create_app
from downcroc.runtime.config.loader import ConfigError, read
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import EventLogger, setup_logging
from downcroc.runtime.paths import Paths, resolve
from downcroc.runtime.service.lock import running

TIMEOUT_S = 5.0


def _settings(paths: Paths) -> Settings:
    if not paths.config_file.exists():
        return Settings()
    try:
        return read(paths.config_file)
    except ConfigError:
        return Settings()


def _served(paths: Paths) -> dict[str, Any] | None:
    info = running(paths.service_file)
    if info is None:
        return None
    try:
        with httpx.Client(timeout=TIMEOUT_S, trust_env=False) as client:
            response = client.get(f"{info.base_url}/openapi.json")
            response.raise_for_status()
            document = response.json()
    except httpx.HTTPError:
        return None
    if not isinstance(document, dict):
        return None
    return document


def _document(paths: Paths, settings: Settings, log: EventLogger) -> dict[str, Any]:
    served = _served(paths)
    if served is not None:
        return served
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

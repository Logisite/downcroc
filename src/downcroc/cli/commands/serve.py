from __future__ import annotations

import sys

from downcroc.runtime.config.loader import ConfigError, load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.paths import ensure, resolve
from downcroc.runtime.service.lifecycle import run_foreground


def run() -> None:
    paths = resolve()
    ensure(paths)
    early = setup_logging(paths, Settings(), stream=sys.stderr)
    try:
        settings, created = load_or_create(paths.config_file)
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        early.error("config.invalid", field=error.field, reason=str(error))
        print(f"config error: {detail}", file=sys.stderr)
        raise SystemExit(1) from error
    log = setup_logging(paths, settings, stream=sys.stderr)
    log.info(
        "config.loaded",
        path=str(paths.config_file),
        first_run=created,
        keys=",".join(settings.model_dump().keys()),
    )
    run_foreground(paths, settings)

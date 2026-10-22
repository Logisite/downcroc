from __future__ import annotations

import sys

from downcroc.cli.context import load
from downcroc.runtime.config.loader import ConfigError
from downcroc.runtime.service.lifecycle import start, status, stop


def _show(report: dict) -> None:
    if report.get("state") == "stopped":
        print("downcroc is not running")
        return
    width = max(len(key) for key in report)
    for key, value in report.items():
        print(f"{key:<{width}}  {value}")


def run(action: str) -> int:
    try:
        paths, settings, _ = load()
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config error: {detail}", file=sys.stderr)
        return 1
    if action == "start":
        try:
            info = start(paths, settings)
        except (OSError, RuntimeError, TimeoutError) as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"started on {info.base_url} (pid {info.pid})")
        return 0
    if action == "stop":
        stopped = stop(paths, settings)
        print("stopped" if stopped else "downcroc was not running")
        return 0
    _show(status(paths))
    return 0

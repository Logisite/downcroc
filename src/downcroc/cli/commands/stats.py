from __future__ import annotations

import sys

import httpx

from downcroc.cli.context import load
from downcroc.runtime.config.loader import ConfigError
from downcroc.runtime.service.registry import read


def rebuild(since: str | None) -> int:
    try:
        paths, settings, _ = load()
    except ConfigError as error:
        detail = f"{error.field}: {error}" if error.field else str(error)
        print(f"config error: {detail}", file=sys.stderr)
        return 1
    info = read(paths.service_file)
    if info is None:
        print("downcroc is not running", file=sys.stderr)
        return 1
    try:
        response = httpx.post(
            f"{info.base_url}/api/stats/rebuild",
            json={"since": since},
            timeout=settings.daemon.stop_timeout_s,
        )
    except httpx.HTTPError as error:
        print(f"cannot reach downcroc: {error}", file=sys.stderr)
        return 1
    if response.status_code >= 400:
        body = response.json()
        detail = body.get("message") if isinstance(body, dict) else response.text
        print(f"rebuild failed: {detail}", file=sys.stderr)
        return 1
    result = response.json()
    print(
        "rebuilt {rows} rows in {duration_ms} ms".format(
            rows=result["rows"],
            duration_ms=result["duration_ms"],
        )
    )
    return 0

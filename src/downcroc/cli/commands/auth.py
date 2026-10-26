from __future__ import annotations

from typing import Any

import httpx

from downcroc.cli.client import token
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record
from downcroc.runtime.service.lock import running

TIMEOUT_S = 5.0


def _report(paths, info) -> dict[str, Any]:
    current = token(paths)
    if info is None:
        return {
            "state": "stopped",
            "token_present": current is not None,
            "accepted": False,
        }
    report: dict[str, Any] = {
        "state": "running",
        "token_present": current is not None,
        "accepted": False,
        "pid": info.pid,
        "url": info.base_url,
    }
    if current is None:
        return report
    try:
        with httpx.Client(
            base_url=info.base_url,
            timeout=TIMEOUT_S,
            trust_env=False,
            headers={"Authorization": f"Bearer {current}"},
        ) as client:
            response = client.get("/api/status")
    except httpx.HTTPError:
        report["state"] = "unreachable"
        return report
    report["accepted"] = response.status_code == 200
    return report


def run(args: object) -> int:
    paths, _, _ = load()
    report = _report(paths, running(paths.service_file))
    if args.json:
        json_out(report)
    else:
        record(report)
    return 0

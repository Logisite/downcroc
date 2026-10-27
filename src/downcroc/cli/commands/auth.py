from __future__ import annotations

from typing import Any

import httpx

from downcroc.cli.client import token
from downcroc.cli.context import load
from downcroc.cli.output import json_out, record
from downcroc.cli.ui.session import build
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


def healthy(report: dict) -> bool:
    return report["state"] == "running" and report["accepted"]


def run(args: object) -> int:
    ui = build(args)
    paths, _, _ = load()
    report = _report(paths, running(paths.service_file))
    ok = healthy(report)
    if ui.json_mode:
        json_out(report)
        return 0 if ok else 1
    if report["state"] == "stopped":
        record({"auth": "downcroc is not running"})
        print("next: downcroc service start")
        return 1
    if report["state"] == "unreachable":
        record({"auth": "the daemon does not answer"})
        print("next: downcroc logs --since 5m")
        return 1
    if not report["token_present"]:
        record({"auth": "no api token"})
        print("next: downcroc service restart")
        return 1
    if not report["accepted"]:
        record({"auth": "the daemon rejected the api token"})
        print("next: downcroc service restart")
        return 1
    record({"auth": "accepted", "daemon": f"pid {report['pid']}, {report['url']}"})
    return 0

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from downcroc.version import API_VERSION, __version__

router = APIRouter(prefix="/api")


def _uptime(request: Request) -> float:
    return round(time.monotonic() - request.app.state.started, 3)


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "api_version": API_VERSION,
        "pid": request.app.state.pid,
        "uptime_s": _uptime(request),
    }


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    return {
        "state": "running",
        "version": __version__,
        "api_version": API_VERSION,
        "pid": request.app.state.pid,
        "started_at": datetime.fromtimestamp(
            request.app.state.started_at, tz=UTC
        ).isoformat(timespec="seconds"),
        "uptime_s": _uptime(request),
    }

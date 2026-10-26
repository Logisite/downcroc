from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["service"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        {
            "error": "unauthorized",
            "message": "the daemon token is required",
            "status": 401,
        },
        status_code=401,
    )


def _authorized(request: Request) -> bool:
    token = getattr(request.app.state, "token", "")
    header = request.headers.get("authorization", "")
    if not token:
        return False
    return secrets.compare_digest(header, f"Bearer {token}")


@router.post("/service/stop", response_model=None)
def stop(
    request: Request,
    background: BackgroundTasks,
) -> dict[str, object] | JSONResponse:
    if not _authorized(request):
        return _unauthorized()
    background.add_task(request.app.state.request_shutdown)
    return {"stopping": True}

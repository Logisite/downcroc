from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

router = APIRouter(prefix="/api", tags=["service"])


@router.post("/service/stop", response_model=None)
def stop(
    request: Request,
    background: BackgroundTasks,
) -> dict[str, object]:
    background.add_task(request.app.state.request_shutdown)
    return {"stopping": True}

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from downcroc.api.schemas.holds import PauseRequest, ResumeRequest

router = APIRouter(prefix="/api", tags=["service"])


def _holds(request: Request):
    return request.app.state.services.holds


@router.post("/service/pause", response_model=None)
def pause(body: PauseRequest, request: Request) -> dict[str, object]:
    state, changed = _holds(request).pause_service(body.reason, body.for_s)
    return {
        "sending": {
            "state": "paused",
            "since": state.sending_paused_at,
            "until": state.sending_paused_until,
            "reason": state.sending_paused_reason,
        },
        "changed": changed,
    }


@router.post("/service/resume", response_model=None)
def resume(body: ResumeRequest, request: Request) -> dict[str, object]:
    state, changed = _holds(request).resume_service(body.reason)
    return {
        "sending": {"state": "running" if not state.paused else "paused"},
        "changed": changed,
    }


@router.post("/service/stop", response_model=None)
def stop(
    request: Request,
    background: BackgroundTasks,
) -> dict[str, object]:
    background.add_task(request.app.state.request_shutdown)
    return {"stopping": True}

from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.backfill import BackfillStatusOut, HoleOut
from downcroc.core.backfill import BackfillService
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/backfill", tags=["backfill"])


def _service(request: Request) -> BackfillService:
    services: Services = request.app.state.services
    return services.backfill_diagnostics


@router.get("/status", response_model=BackfillStatusOut)
def status(request: Request) -> BackfillStatusOut:
    return BackfillStatusOut.of(_service(request).status())


@router.get("/holes/{attempt_id}", response_model=HoleOut)
def explain(attempt_id: str, request: Request) -> HoleOut:
    return HoleOut.of(_service(request).explain(attempt_id))


@router.post("/holes/{attempt_id}/retry", response_model=HoleOut)
def retry(attempt_id: str, request: Request) -> HoleOut:
    return HoleOut.of(_service(request).retry(attempt_id))

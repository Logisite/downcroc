from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("/transports")
def doctor_transports(request: Request) -> dict[str, object]:
    return _services(request).doctor.transports()


@router.get("/capacity")
def doctor_capacity(request: Request) -> dict[str, object]:
    return _services(request).doctor.capacity()


@router.get("/inbound")
def doctor_inbound(request: Request) -> dict[str, object]:
    return _services(request).doctor.inbound()

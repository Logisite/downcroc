from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.schemas.failures import FailureOut, FailureRetryAll
from downcroc.api.schemas.jobs import JobOut
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/failed", tags=["failures"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("", response_model=list[FailureOut])
def list_failures(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[FailureOut]:
    return [
        FailureOut.of(failure)
        for failure in _services(request).failures.list(limit=limit)
    ]


@router.post("/retry", response_model=FailureRetryAll)
def retry_all_failures(request: Request) -> FailureRetryAll:
    return FailureRetryAll(retried=_services(request).failures.retry_all())


@router.get("/{job_id}", response_model=FailureOut)
def get_failure(job_id: str, request: Request) -> FailureOut:
    return FailureOut.of(_services(request).failures.get(job_id))


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_failure(job_id: str, request: Request) -> JobOut:
    return JobOut.of(_services(request).failures.retry(job_id))

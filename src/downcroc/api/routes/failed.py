from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.confirm import require
from downcroc.api.schemas.failures import (
    FailureForgetOut,
    FailureOut,
    FailurePurgeOut,
    FailurePurgeRequest,
    FailureRetryAll,
)
from downcroc.api.schemas.jobs import JobOut
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/failed", tags=["failures"])
aliases = APIRouter(prefix="/api/failures", tags=["failures"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("", response_model=list[FailureOut])
def list_failures(
    request: Request,
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[FailureOut]:
    service = _services(request).failures
    failures = service.list(limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(service.count())
    return [FailureOut.of(failure) for failure in failures]


@router.post("/retry", response_model=FailureRetryAll)
def retry_all_failures(request: Request) -> FailureRetryAll:
    return FailureRetryAll(retried=_services(request).failures.retry_all())


@router.post("/purge", response_model=FailurePurgeOut)
@aliases.post("/purge", response_model=FailurePurgeOut)
def purge_failures(
    body: FailurePurgeRequest,
    request: Request,
    confirm: bool = Query(default=False),
) -> FailurePurgeOut:
    if not body.dry_run:
        require(confirm or body.confirm)
    result = _services(request).failures.purge(
        states=body.states or None,
        older_than_days=body.older_than_days,
        dry_run=body.dry_run,
    )
    return FailurePurgeOut(**result)


@router.get("/{job_id}", response_model=FailureOut)
def get_failure(job_id: str, request: Request) -> FailureOut:
    return FailureOut.of(_services(request).failures.get(job_id))


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_failure(job_id: str, request: Request) -> JobOut:
    return JobOut.of(_services(request).failures.retry(job_id))


@router.delete("/{job_id}", response_model=FailureForgetOut)
@aliases.delete("/{job_id}", response_model=FailureForgetOut)
def forget_failure(
    job_id: str, request: Request, confirm: bool = Query(default=False)
) -> FailureForgetOut:
    require(confirm)
    return FailureForgetOut(**_services(request).failures.forget(job_id))

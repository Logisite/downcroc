from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.schemas.jobs import JobCreate, JobOut
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("", response_model=list[JobOut])
def list_jobs(
    request: Request,
    response: Response,
    batch: str | None = None,
    account: str | None = None,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[JobOut]:
    service = _services(request).outbound
    jobs = service.list(
        batch_id=batch,
        account_id=account,
        state=state,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(
        service.count(batch_id=batch, account_id=account, state=state)
    )
    return [JobOut.of(job) for job in jobs]


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, request: Request) -> JobOut:
    job = _services(request).outbound.create(
        account_id=body.account_id,
        recipient=body.recipient,
        recipient_name=body.recipient_name,
        subject=body.subject,
        text=body.text,
        html=body.html,
        batch_id=body.batch_id,
    )
    return JobOut.of(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request) -> JobOut:
    return JobOut.of(_services(request).outbound.get(job_id))


@router.post("/{job_id}/send", response_model=JobOut)
async def send_job(job_id: str, request: Request) -> JobOut:
    job = await _services(request).outbound.send(job_id)
    return JobOut.of(job)

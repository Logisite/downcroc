from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.confirm import require
from downcroc.api.schemas.jobs import (
    JobCreate,
    JobDeleteOut,
    JobDeletionOut,
    JobOut,
    ReassignOut,
    ReassignRequest,
)
from downcroc.core.bootstrap import Services
from downcroc.core.portability import Selection

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


@router.get("/deletion", response_model=JobDeletionOut)
def deletion_preview(
    request: Request,
    account_id: str | None = None,
    state: str | None = None,
) -> JobDeletionOut:
    preview = _services(request).portability.deletion_preview(
        account_id=account_id, state=state
    )
    return JobDeletionOut(**preview)


@router.post("/reassign", response_model=ReassignOut)
def reassign_jobs(
    body: ReassignRequest,
    request: Request,
    confirm: bool = Query(default=False),
) -> ReassignOut:
    if not body.dry_run:
        require(confirm or body.confirm)
    result = _services(request).portability.reassign(
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        selection=Selection(
            job_ids=body.job_ids or None,
            batch_ids=body.batch_ids or None,
            states=body.states or None,
            created_since=body.created_since,
            created_until=body.created_until,
        ),
        include_failed=body.include_failed,
        force=body.force,
        dry_run=body.dry_run,
    )
    return ReassignOut(**result)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, request: Request) -> JobOut:
    return JobOut.of(_services(request).portability.cancel_job(job_id))


@router.delete("/{job_id}", response_model=JobDeleteOut)
def delete_job(
    job_id: str,
    request: Request,
    confirm: bool = Query(default=False),
    force: bool = False,
    dry_run: bool = False,
) -> JobDeleteOut:
    if not dry_run:
        require(confirm)
    result = _services(request).portability.delete_job(
        job_id, force=force, dry_run=dry_run
    )
    return JobDeleteOut(**result)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request) -> JobOut:
    return JobOut.of(_services(request).outbound.get(job_id))


@router.post("/{job_id}/send", response_model=JobOut)
async def send_job(job_id: str, request: Request) -> JobOut:
    job = await _services(request).outbound.send(job_id)
    return JobOut.of(job)

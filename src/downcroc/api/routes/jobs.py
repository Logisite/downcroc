from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.confirm import require
from downcroc.api.schemas.holds import PauseRequest, ResumeRequest
from downcroc.api.schemas.jobs import (
    JobCreate,
    JobDeleteOut,
    JobDeletionOut,
    JobOut,
    ReassignOut,
    ReassignRequest,
    SendAttemptOut,
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
    capacity = _services(request).capacity
    return [JobOut.of(job, capacity.job_eta(job)) for job in jobs]


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
        pin=body.pin,
        unpin=body.unpin,
        force=body.force,
        dry_run=body.dry_run,
    )
    return ReassignOut(**result)


@router.get("/{job_id}/attempts", response_model=list[SendAttemptOut])
def job_attempts(job_id: str, request: Request) -> list[SendAttemptOut]:
    services = _services(request)
    services.outbound.get(job_id)
    return [
        SendAttemptOut.model_validate(attempt)
        for attempt in services.send_attempts.list_for_job(job_id)
    ]


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


@router.post("/{job_id}/pause", response_model=JobOut)
def pause_job(job_id: str, body: PauseRequest, request: Request) -> JobOut:
    services = _services(request)
    job, _ = services.holds.pause_job(job_id, body.reason)
    return JobOut.of(job, services.capacity.job_eta(job))


@router.post("/{job_id}/resume", response_model=JobOut)
def resume_job(job_id: str, body: ResumeRequest, request: Request) -> JobOut:
    services = _services(request)
    job, _ = services.holds.resume_job(job_id, body.reason)
    return JobOut.of(job, services.capacity.job_eta(job))


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request) -> JobOut:
    services = _services(request)
    job = services.outbound.get(job_id)
    return JobOut.of(job, services.capacity.job_eta(job))


@router.post("/{job_id}/send", response_model=JobOut)
async def send_job(job_id: str, request: Request) -> JobOut:
    services = _services(request)
    current = services.outbound.get(job_id)
    services.holds.ensure_can_send(
        job_id=job_id,
        account_id=current.account_id,
        batch_id=services.outbound.hold_batch_id(current),
    )
    job = await services.outbound.send(job_id)
    return JobOut.of(job, services.capacity.job_eta(job))

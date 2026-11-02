from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from downcroc.api.confirm import require
from downcroc.api.schemas.batches import (
    ApproveRequest,
    BatchDeleteOut,
    BatchDetailOut,
    BatchOut,
    BatchReassignOut,
    BatchReassignRequest,
    BatchSubmit,
    FollowUpRequest,
    PreviewOut,
    SuppressionPreviewOut,
)
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/batches", tags=["batches"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.post("", response_model=BatchDetailOut, status_code=201)
def submit_batch(
    body: BatchSubmit, request: Request, response: Response
) -> BatchDetailOut:
    detail = _services(request).batches.submit(
        body.path, body.template, body.account, body.key
    )
    if detail.reused:
        response.status_code = 200
    capacity = _services(request).capacity
    return BatchDetailOut.from_detail(
        detail,
        capacity.batch_eta(detail.batch),
        capacity.selection(
            sum(detail.counts.values()),
            account_ids=[detail.batch.account_id] if detail.batch.account_id else None,
            pinned=detail.batch.account_id is not None,
        ),
    )


@router.post("/preview", response_model=PreviewOut)
def preview_batch(
    body: BatchSubmit,
    request: Request,
    key: str | None = None,
    all: bool = False,
) -> PreviewOut:
    preview = _services(request).batches.preview(
        body.path, body.template, key, body.account, all
    )
    capacity = _services(request).capacity
    account_ids = [body.account] if body.account else None
    return PreviewOut.of(
        preview,
        capacity.selection(
            preview.valid,
            account_ids=account_ids,
            pinned=body.account is not None,
        ),
    )


@router.get("", response_model=list[BatchOut])
def list_batches(
    request: Request,
    response: Response,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[BatchOut]:
    service = _services(request).batches
    response.headers["X-Total-Count"] = str(service.count(state=state))
    capacity = _services(request).capacity
    return [
        BatchOut.of(batch, service.counts(batch.id), capacity.batch_eta(batch))
        for batch in service.list(state=state, limit=limit, offset=offset)
    ]


@router.get("/{batch_id}", response_model=BatchDetailOut)
def get_batch(batch_id: str, request: Request) -> BatchDetailOut:
    services = _services(request)
    detail = services.batches.detail(batch_id)
    capacity = services.capacity
    return BatchDetailOut.from_detail(
        detail,
        capacity.batch_eta(detail.batch),
        capacity.selection(
            sum(detail.counts.values()),
            account_ids=[detail.batch.account_id] if detail.batch.account_id else None,
            pinned=detail.batch.account_id is not None,
        ),
    )


@router.post("/{batch_id}/approve", response_model=BatchDetailOut)
async def approve_batch(
    batch_id: str, body: ApproveRequest, request: Request
) -> BatchDetailOut:
    detail = await _services(request).batches.approve(batch_id, body.mode)
    return BatchDetailOut.from_detail(detail)


@router.post("/{batch_id}/cancel", response_model=BatchDetailOut)
def cancel_batch(batch_id: str, request: Request) -> BatchDetailOut:
    return BatchDetailOut.from_detail(_services(request).batches.cancel(batch_id))


@router.post("/{batch_id}/reassign", response_model=BatchReassignOut)
def reassign_batch(
    batch_id: str,
    body: BatchReassignRequest,
    request: Request,
    confirm: bool = Query(default=False),
) -> BatchReassignOut:
    if not body.dry_run:
        require(confirm or body.confirm)
    result = _services(request).portability.reassign_batch(
        batch_id,
        to_account_id=body.to_account_id,
        states=body.states or None,
        include_failed=body.include_failed,
        force=body.force,
        dry_run=body.dry_run,
    )
    return BatchReassignOut(**result)


@router.delete("/{batch_id}", response_model=BatchDeleteOut)
def delete_batch(
    batch_id: str,
    request: Request,
    confirm: bool = Query(default=False),
    dry_run: bool = False,
) -> BatchDeleteOut:
    if not dry_run:
        require(confirm)
    result = _services(request).portability.delete_batch(batch_id, dry_run=dry_run)
    return BatchDeleteOut(**result)


@router.post("/{batch_id}/followups", response_model=BatchDetailOut, status_code=201)
def create_followup(
    batch_id: str, body: FollowUpRequest, request: Request
) -> BatchDetailOut:
    services = _services(request)
    created = services.followups.create_from_payload(
        batch_id,
        path=body.path,
        template=body.template,
        step=body.step,
        require_approval=body.require_approval,
    )
    return BatchDetailOut.from_detail(services.batches.detail(created))


@router.get(
    "/{batch_id}/suppression-preview",
    response_model=list[SuppressionPreviewOut],
)
def suppression_preview(batch_id: str, request: Request) -> list[SuppressionPreviewOut]:
    entries = _services(request).batches.suppression_preview(batch_id)
    return [SuppressionPreviewOut(**entry) for entry in entries]

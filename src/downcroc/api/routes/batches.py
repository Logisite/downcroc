from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.schemas.batches import (
    ApproveRequest,
    BatchDetailOut,
    BatchOut,
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
def submit_batch(body: BatchSubmit, request: Request) -> BatchDetailOut:
    detail = _services(request).batches.submit(body.path, body.template)
    return BatchDetailOut.from_detail(detail)


@router.post("/preview", response_model=PreviewOut)
def preview_batch(
    body: BatchSubmit, request: Request, key: str | None = None
) -> PreviewOut:
    preview = _services(request).batches.preview(body.path, body.template, key)
    return PreviewOut.of(preview)


@router.get("", response_model=list[BatchOut])
def list_batches(
    request: Request,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BatchOut]:
    service = _services(request).batches
    return [
        BatchOut.of(batch, service.counts(batch.id))
        for batch in service.list(state=state, limit=limit)
    ]


@router.get("/{batch_id}", response_model=BatchDetailOut)
def get_batch(batch_id: str, request: Request) -> BatchDetailOut:
    return BatchDetailOut.from_detail(_services(request).batches.detail(batch_id))


@router.post("/{batch_id}/approve", response_model=BatchDetailOut)
async def approve_batch(
    batch_id: str, body: ApproveRequest, request: Request
) -> BatchDetailOut:
    detail = await _services(request).batches.approve(batch_id, body.mode)
    return BatchDetailOut.from_detail(detail)


@router.post("/{batch_id}/cancel", response_model=BatchDetailOut)
def cancel_batch(batch_id: str, request: Request) -> BatchDetailOut:
    return BatchDetailOut.from_detail(_services(request).batches.cancel(batch_id))


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

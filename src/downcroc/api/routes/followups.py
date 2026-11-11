from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.confirm import require
from downcroc.api.schemas.followups import (
    FollowUpDeclareRequest,
    FollowUpStatusOut,
)
from downcroc.core.bootstrap import Services

router = APIRouter(prefix="/api/batches", tags=["followups"])


def _services(request: Request) -> Services:
    return request.app.state.services


@router.get("/{batch_id}/followups", response_model=FollowUpStatusOut)
def followup_status(batch_id: str, request: Request) -> FollowUpStatusOut:
    return FollowUpStatusOut.of(_services(request).followups.status(batch_id))


@router.put("/{batch_id}/followups/{step}", response_model=FollowUpStatusOut)
def declare_followup(
    batch_id: str,
    step: str,
    body: FollowUpDeclareRequest,
    request: Request,
) -> FollowUpStatusOut:
    report = _services(request).followups.declare(
        batch_id,
        step,
        path=body.path,
        kind=body.kind,
        version=body.version,
        dry_run=body.dry_run,
    )
    return FollowUpStatusOut.of(report)


@router.delete("/{batch_id}/followups/{step}", response_model=FollowUpStatusOut)
def remove_followup(
    batch_id: str,
    step: str,
    request: Request,
    confirm: bool = Query(default=False),
    version: int | None = Query(default=None, ge=1),
    dry_run: bool = False,
) -> FollowUpStatusOut:
    if not dry_run:
        require(confirm)
    report = _services(request).followups.remove(
        batch_id, step, version=version, dry_run=dry_run
    )
    return FollowUpStatusOut.of(report)


@router.post(
    "/{batch_id}/followups/{step}/retire",
    response_model=FollowUpStatusOut,
)
def retire_followup(
    batch_id: str,
    step: str,
    request: Request,
    confirm: bool = Query(default=False),
    version: int | None = Query(default=None, ge=1),
    dry_run: bool = False,
) -> FollowUpStatusOut:
    report = _services(request).followups.retire(
        batch_id,
        step,
        version=version,
        confirm=confirm,
        dry_run=dry_run,
    )
    return FollowUpStatusOut.of(report)

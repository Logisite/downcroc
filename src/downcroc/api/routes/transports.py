from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.confirm import require
from downcroc.api.schemas.accounts import (
    TransportCreate,
    TransportOut,
    TransportTestOut,
    TransportUpdate,
)
from downcroc.core.transports import TransportService
from downcroc.domain.transports import TransportKind
from downcroc.store.repositories.transports import TransportInvalid

router = APIRouter(
    prefix="/api/accounts/{account_id}/transports",
    tags=["transports"],
)


def _service(request: Request) -> TransportService:
    return request.app.state.services.transports


@router.get("", response_model=list[TransportOut])
def list_transports(account_id: str, request: Request) -> list[TransportOut]:
    return [TransportOut.of(item) for item in _service(request).list(account_id)]


@router.post("", response_model=TransportOut, status_code=201)
def add_transport(
    account_id: str, body: TransportCreate, request: Request
) -> TransportOut:
    try:
        kind = TransportKind(body.kind)
    except ValueError as error:
        raise TransportInvalid(f"unknown transport {body.kind}") from error
    binding = _service(request).add(
        account_id,
        kind=kind,
        priority=body.priority,
        max_concurrency=body.max_concurrency,
        rate_per_min=body.rate_per_min,
        oauth_client_id=body.oauth_client_id,
    )
    return TransportOut.of(binding)


@router.get("/{binding_id}", response_model=TransportOut)
def get_transport(account_id: str, binding_id: str, request: Request) -> TransportOut:
    return TransportOut.of(_service(request).get(account_id, binding_id))


@router.patch("/{binding_id}", response_model=TransportOut)
def update_transport(
    account_id: str,
    binding_id: str,
    body: TransportUpdate,
    request: Request,
) -> TransportOut:
    binding = _service(request).update(
        account_id,
        binding_id,
        priority=body.priority,
        max_concurrency=body.max_concurrency,
        rate_per_min=body.rate_per_min,
        enabled=body.enabled,
    )
    return TransportOut.of(binding)


@router.delete("/{binding_id}", response_model=TransportOut)
def remove_transport(
    account_id: str,
    binding_id: str,
    request: Request,
    confirm: bool = Query(default=False),
) -> TransportOut:
    require(confirm)
    return TransportOut.of(_service(request).remove(account_id, binding_id))


@router.post("/{binding_id}/test", response_model=TransportTestOut)
async def test_transport(
    account_id: str, binding_id: str, request: Request
) -> TransportTestOut:
    result = await _service(request).test(account_id, binding_id)
    return TransportTestOut(**result)

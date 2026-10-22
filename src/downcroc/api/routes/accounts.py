from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import Response

from downcroc.api.schemas.accounts import (
    AccountCreate,
    AccountOut,
    AppPasswordConnect,
    AttemptOut,
)
from downcroc.core.accounts_service import AccountsService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _service(request: Request) -> AccountsService:
    return request.app.state.services.accounts


@router.get("", response_model=list[AccountOut])
def list_accounts(request: Request) -> list[AccountOut]:
    return [AccountOut.of(account) for account in _service(request).list()]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, request: Request) -> AccountOut:
    account = _service(request).create(body.provider, body.address, body.label)
    return AccountOut.of(account)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: str, request: Request) -> AccountOut:
    return AccountOut.of(_service(request).get(account_id))


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: str, request: Request) -> Response:
    _service(request).delete(account_id)
    return Response(status_code=204)


@router.post("/{account_id}/attempts", response_model=AttemptOut, status_code=201)
def start_attempt(account_id: str, request: Request) -> AttemptOut:
    return AttemptOut.of(_service(request).start_attempt(account_id))


@router.post("/{account_id}/connect", response_model=AccountOut)
def connect_password(
    account_id: str, body: AppPasswordConnect, request: Request
) -> AccountOut:
    account = _service(request).connect_password(account_id, body.password)
    return AccountOut.of(account)


@router.post("/{account_id}/verify", response_model=AccountOut)
def verify_account(
    account_id: str, request: Request, refresh: bool = False
) -> AccountOut:
    return AccountOut.of(_service(request).verify(account_id, refresh=refresh))

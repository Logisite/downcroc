from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.confirm import require
from downcroc.api.schemas.accounts import (
    AccountCreate,
    AccountDeleteOut,
    AccountDeletionOut,
    AccountOut,
    AppPasswordConnect,
    AttemptOut,
    WatcherToggle,
)
from downcroc.core.accounts_service import AccountsService
from downcroc.core.policy import PolicyResolver
from downcroc.domain.accounts import Account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _service(request: Request) -> AccountsService:
    return request.app.state.services.accounts


def _policy(request: Request) -> PolicyResolver:
    return request.app.state.services.policy


def _out(request: Request, account: Account) -> AccountOut:
    return AccountOut.of(account, _policy(request).effective(account))


@router.get("", response_model=list[AccountOut])
def list_accounts(request: Request) -> list[AccountOut]:
    return [_out(request, account) for account in _service(request).list()]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, request: Request) -> AccountOut:
    account = _service(request).create(body.provider, body.address, body.label)
    return _out(request, account)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: str, request: Request) -> AccountOut:
    return _out(request, _service(request).get(account_id))


@router.get("/{account_id}/deletion", response_model=AccountDeletionOut)
def preview_account_deletion(account_id: str, request: Request) -> AccountDeletionOut:
    return AccountDeletionOut(**_service(request).deletion_preview(account_id))


@router.delete("/{account_id}", response_model=AccountDeleteOut)
def delete_account(
    account_id: str,
    request: Request,
    confirm: bool = Query(default=False),
    reassign_to: str | None = None,
    force_jobs: bool = False,
    force_history: bool = False,
) -> AccountDeleteOut:
    require(confirm)
    result = _service(request).delete(
        account_id,
        reassign_to=reassign_to,
        force_jobs=force_jobs,
        force_history=force_history,
    )
    return AccountDeleteOut(**result)


@router.post("/{account_id}/archive", response_model=AccountOut)
def archive_account(
    account_id: str, request: Request, confirm: bool = Query(default=False)
) -> AccountOut:
    require(confirm)
    return _out(request, _service(request).archive(account_id))


@router.post("/{account_id}/unarchive", response_model=AccountOut)
def unarchive_account(
    account_id: str, request: Request, confirm: bool = Query(default=False)
) -> AccountOut:
    require(confirm)
    return _out(request, _service(request).unarchive(account_id))


@router.post("/{account_id}/attempts", response_model=AttemptOut, status_code=201)
def start_attempt(
    account_id: str,
    request: Request,
    client_id: str | None = None,
) -> AttemptOut:
    attempt = _service(request).start_attempt(account_id, client_id)
    return AttemptOut.of(attempt)


@router.post("/{account_id}/connect", response_model=AccountOut)
def connect_password(
    account_id: str, body: AppPasswordConnect, request: Request
) -> AccountOut:
    account = _service(request).connect_password(account_id, body.password)
    return _out(request, account)


@router.post("/{account_id}/verify", response_model=AccountOut)
def verify_account(
    account_id: str, request: Request, refresh: bool = False
) -> AccountOut:
    return _out(request, _service(request).verify(account_id, refresh=refresh))


@router.patch("/{account_id}/watcher", response_model=AccountOut)
def set_watcher(account_id: str, body: WatcherToggle, request: Request) -> AccountOut:
    return _out(request, _service(request).set_watcher(account_id, body.enabled))


@router.post("/{account_id}/sync", response_model=AccountOut, status_code=202)
def sync_account(account_id: str, request: Request) -> AccountOut:
    return _out(request, _service(request).sync(account_id))

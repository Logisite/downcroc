from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.vault import (
    VaultAccount,
    VaultInit,
    VaultOut,
    VaultUnlock,
)
from downcroc.core.vault import VaultService

router = APIRouter(prefix="/api/vault", tags=["vault"])


def _service(request: Request) -> VaultService:
    return request.app.state.services.vault


def _out(request: Request) -> VaultOut:
    accounts = [
        VaultAccount(id=account.id, credential_present=account.credential_present)
        for account in request.app.state.services.accounts.list()
    ]
    return VaultOut.of(_service(request).status(), accounts)


@router.get("", response_model=VaultOut)
def read_vault(request: Request) -> VaultOut:
    return _out(request)


@router.post("/init", response_model=VaultOut, status_code=201)
async def init(body: VaultInit, request: Request) -> VaultOut:
    _service(request).initialize(body.password)
    request.app.state.services.inbound.start_all()
    await request.app.state.services.outbound.reconcile()
    return _out(request)


@router.post("/unlock", response_model=VaultOut)
async def unlock(body: VaultUnlock, request: Request) -> VaultOut:
    _service(request).unlock(body.password)
    request.app.state.services.vault_maintenance.on_unlock()
    request.app.state.services.inbound.start_all()
    await request.app.state.services.outbound.reconcile()
    return _out(request)


@router.post("/lock", response_model=VaultOut)
async def lock(request: Request) -> VaultOut:
    request.app.state.services.inbound.stop_all("vault_locked")
    await request.app.state.services.outbound.close_sessions("vault_locked")
    _service(request).lock("api")
    return _out(request)

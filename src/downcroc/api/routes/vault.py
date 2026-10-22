from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.vault import VaultAccount, VaultOut, VaultUnlock
from downcroc.core.vault_service import VaultService

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


@router.post("/unlock", response_model=VaultOut)
def unlock(body: VaultUnlock, request: Request) -> VaultOut:
    _service(request).unlock(body.password)
    request.app.state.services.accounts.prune_orphans()
    return _out(request)


@router.post("/lock", response_model=VaultOut)
def lock(request: Request) -> VaultOut:
    _service(request).lock("api")
    return _out(request)

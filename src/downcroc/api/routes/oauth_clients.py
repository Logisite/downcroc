from __future__ import annotations

from fastapi import APIRouter, Query, Request

from downcroc.api.confirm import require
from downcroc.api.schemas.accounts import AttemptOut
from downcroc.api.schemas.oauth_clients import (
    OAuthAuthorize,
    OAuthClientDependentOut,
    OAuthClientImport,
    OAuthClientOut,
)
from downcroc.core.accounts import AccountsService
from downcroc.core.oauth_clients import OAuthClientService

router = APIRouter(prefix="/api/oauth-clients", tags=["oauth-clients"])


def _service(request: Request) -> OAuthClientService:
    return request.app.state.services.oauth_clients


@router.get("", response_model=list[OAuthClientOut])
def list_clients(
    request: Request, provider_id: str | None = None
) -> list[OAuthClientOut]:
    return [OAuthClientOut.of(item) for item in _service(request).list(provider_id)]


@router.post("", response_model=OAuthClientOut, status_code=201)
def import_client(body: OAuthClientImport, request: Request) -> OAuthClientOut:
    client = _service(request).import_json(body.provider_id, body.payload, body.label)
    return OAuthClientOut.of(client)


@router.get("/{client_id}", response_model=OAuthClientOut)
def get_client(client_id: str, request: Request) -> OAuthClientOut:
    return OAuthClientOut.of(_service(request).get(client_id))


@router.get("/{client_id}/dependents", response_model=list[OAuthClientDependentOut])
def list_dependents(client_id: str, request: Request) -> list[OAuthClientDependentOut]:
    rows = _service(request).dependent_rows(client_id)
    return [OAuthClientDependentOut(**row) for row in rows]


@router.post("/{client_id}/authorize", response_model=AttemptOut, status_code=201)
def authorize(client_id: str, body: OAuthAuthorize, request: Request) -> AttemptOut:
    """Start or resume the mailbox OAuth flow for an imported client."""
    accounts: AccountsService = request.app.state.services.accounts
    attempt = accounts.start_attempt(
        body.account_id,
        client_id,
        body.transport,
    )
    return AttemptOut.of(attempt)


@router.post("/{client_id}/revoke", response_model=OAuthClientOut)
def revoke_client(
    client_id: str, request: Request, confirm: bool = Query(default=False)
) -> OAuthClientOut:
    require(confirm)
    return OAuthClientOut.of(_service(request).revoke(client_id))


@router.delete("/{client_id}", response_model=OAuthClientOut)
def delete_client(
    client_id: str,
    request: Request,
    confirm: bool = Query(default=False),
    force: bool = False,
) -> OAuthClientOut:
    require(confirm)
    return OAuthClientOut.of(_service(request).delete(client_id, force=force))

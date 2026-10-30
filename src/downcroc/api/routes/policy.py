from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.policy import PolicyOut, PolicyOverrideIn
from downcroc.core.policy_service import PolicyService

router = APIRouter(tags=["policy"])


def _service(request: Request) -> PolicyService:
    return request.app.state.services.policy_overrides


@router.get("/api/accounts/{account_id}/policy", response_model=PolicyOut)
def show_account_policy(account_id: str, request: Request) -> PolicyOut:
    return PolicyOut.build(_service(request).account_view(account_id))


@router.put("/api/accounts/{account_id}/policy", response_model=PolicyOut)
def set_account_policy(
    account_id: str, body: PolicyOverrideIn, request: Request
) -> PolicyOut:
    view = _service(request).set_account(account_id, body.override(), for_s=body.for_s)
    return PolicyOut.build(view)


@router.delete("/api/accounts/{account_id}/policy", response_model=PolicyOut)
def clear_account_policy(account_id: str, request: Request) -> PolicyOut:
    return PolicyOut.build(_service(request).clear_account(account_id))


@router.delete("/api/accounts/{account_id}/policy/temporary", response_model=PolicyOut)
def clear_account_temporary(account_id: str, request: Request) -> PolicyOut:
    return PolicyOut.build(_service(request).clear_account_temporary(account_id))


@router.get("/api/sending", response_model=PolicyOut)
def show_sending(request: Request) -> PolicyOut:
    return PolicyOut.build(_service(request).global_view())


@router.put("/api/sending", response_model=PolicyOut)
def set_sending(body: PolicyOverrideIn, request: Request) -> PolicyOut:
    return PolicyOut.build(
        _service(request).set_global(body.override(), for_s=body.for_s)
    )


@router.delete("/api/sending", response_model=PolicyOut)
def clear_sending(request: Request) -> PolicyOut:
    return PolicyOut.build(_service(request).clear_global())

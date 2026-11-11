from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.accounts import AttemptOut
from downcroc.core.accounts import AccountsService

router = APIRouter(prefix="/api/attempts", tags=["accounts"])


def _service(request: Request) -> AccountsService:
    return request.app.state.services.accounts


@router.get("/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: str, request: Request) -> AttemptOut:
    return AttemptOut.of(_service(request).attempt(attempt_id))


@router.post("/{attempt_id}/cancel", response_model=AttemptOut)
def cancel_attempt(attempt_id: str, request: Request) -> AttemptOut:
    return AttemptOut.of(_service(request).cancel_attempt(attempt_id))


@router.delete("/{attempt_id}", response_model=AttemptOut)
def delete_attempt(attempt_id: str, request: Request) -> AttemptOut:
    """Cancel and discard a pending OAuth attempt.

    A stale attempt must never block the next ``account connect``. Cancelling is
    the same operation whether the caller thinks of it as a delete or a cancel.
    """
    return AttemptOut.of(_service(request).cancel_attempt(attempt_id))

from __future__ import annotations

from fastapi import APIRouter, Request

from downcroc.api.schemas.accounts import ProviderOut
from downcroc.providers.registry import ProviderRegistry

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _registry(request: Request) -> ProviderRegistry:
    return request.app.state.services.providers


@router.get("", response_model=list[ProviderOut])
def list_providers(request: Request) -> list[ProviderOut]:
    return [ProviderOut.of(spec) for spec in _registry(request).list()]

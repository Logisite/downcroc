from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import Response

from downcroc.api.schemas.accounts import ProviderIn, ProviderOut
from downcroc.core.bootstrap import Services
from downcroc.domain.errors import (
    ProviderConfigError,
    ProviderInUse,
    ProviderInvalid,
    ProviderUnknown,
)
from downcroc.providers.registry import ProviderRegistry

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _services(request: Request) -> Services:
    return request.app.state.services


def _registry(request: Request) -> ProviderRegistry:
    return _services(request).providers


def _out(services: Services, provider_id: str) -> ProviderOut:
    spec = services.providers.get(provider_id)
    source = services.providers.source_of(provider_id)
    imported = bool(services.oauth_clients.list(provider_id))
    return ProviderOut.of(
        spec,
        source=str(source) if source else None,
        oauth_client_imported=imported,
    )


@router.get("", response_model=list[ProviderOut])
def list_providers(request: Request) -> list[ProviderOut]:
    services = _services(request)
    return [_out(services, spec.id) for spec in services.providers.list()]


@router.get("/{provider_id}", response_model=ProviderOut)
def get_provider(provider_id: str, request: Request) -> ProviderOut:
    return _out(_services(request), provider_id)


@router.post("/reload", response_model=list[ProviderOut])
def reload_providers(request: Request) -> list[ProviderOut]:
    registry = _registry(request)
    try:
        registry.reload()
    except ProviderConfigError as error:
        raise ProviderInvalid(
            error.message,
            hint="fix the field and run `downcroc provider list`",
            fields={
                "path": str(error.path) if error.path else "",
                "field": error.field or "",
            },
        ) from error
    return list_providers(request)


@router.put("/{provider_id}", response_model=ProviderOut)
def put_provider(provider_id: str, body: ProviderIn, request: Request) -> ProviderOut:
    registry = _registry(request)
    values = body.model_dump(exclude_none=True)
    if not registry.has(provider_id):
        values.setdefault("label", provider_id)
        values.setdefault("imap_port", 993)
        values.setdefault("imap_tls", "ssl")
        values.setdefault("auth_kind", "app_password")
    try:
        registry.save(provider_id, values)
    except ProviderConfigError as error:
        raise ProviderInvalid(
            error.message,
            hint="fill the required fields for this door",
            fields={
                "path": str(error.path) if error.path else "",
                "field": error.field or "",
            },
        ) from error
    return _out(_services(request), provider_id)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: str, request: Request) -> Response:
    services = _services(request)
    in_use = [
        account.id
        for account in services.accounts.list()
        if account.provider == provider_id
    ]
    if in_use:
        raise ProviderInUse(
            "accounts still use this provider",
            hint="delete or move those accounts first",
            fields={"provider": provider_id, "accounts": ", ".join(in_use)},
        )
    if services.providers.source_of(provider_id) is None:
        raise ProviderUnknown(
            "the provider is not declared in your config",
            hint="only providers you added can be removed",
            fields={"provider": provider_id},
        )
    services.providers.remove(provider_id)
    return Response(status_code=204)

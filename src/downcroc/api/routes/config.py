from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request

from downcroc.api.schemas.config import (
    ConfigFieldOut,
    ConfigOut,
    ConfigPatchOut,
    ConfigSchemaOut,
)
from downcroc.core.config_service import ConfigService

router = APIRouter(prefix="/api/config", tags=["config"])


def _service(request: Request) -> ConfigService:
    return request.app.state.services.config


@router.get("/schema", response_model=ConfigSchemaOut)
def config_schema(request: Request) -> ConfigSchemaOut:
    fields = [ConfigFieldOut(**field) for field in _service(request).fields()]
    return ConfigSchemaOut(fields=fields)


@router.get("", response_model=ConfigOut)
def get_config(request: Request) -> ConfigOut:
    return ConfigOut(**_service(request).snapshot())


@router.patch("", response_model=ConfigPatchOut)
def patch_config(
    request: Request,
    body: Annotated[dict[str, Any], Body()],
) -> ConfigPatchOut:
    service = _service(request)
    result = service.patch(body)
    return ConfigPatchOut(
        changed=result.changed,
        config=request.app.state.settings.model_dump(mode="json"),
    )

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


def _host(request: Request):
    host = request.app.state.services.extensions
    if host is None:
        raise RuntimeError("extension host is not available")
    return host


@router.get("")
def list_extensions(request: Request) -> list[dict[str, Any]]:
    return _host(request).status()


@router.get("/capabilities")
def capabilities(request: Request) -> dict[str, Any]:
    return {"capabilities": list(_host(request).broker.capabilities)}


@router.post("/reload")
def reload_extensions(request: Request) -> dict[str, Any]:
    _host(request).reload()
    return {"ok": True}


@router.post("/{extension}/enable")
def enable_extension(extension: str, request: Request) -> dict[str, Any]:
    _host(request).enable(extension)
    return {"ok": True}


@router.post("/{extension}/disable")
def disable_extension(extension: str, request: Request) -> dict[str, Any]:
    _host(request).disable(extension)
    return {"ok": True}


@router.post("/{extension}/test")
def test_extension(extension: str, body: dict[str, Any], request: Request) -> Any:
    return _host(request).run_once(extension, body)


@router.post("/{extension}/command/{command}")
def run_command(
    extension: str, command: str, body: dict[str, Any], request: Request
) -> Any:
    return _host(request).invoke(extension, command, body)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from downcroc.extensions.tiers import tier_for

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
    return {
        "capabilities": [
            {"name": name, "tier": tier_for(name)}
            for name in _host(request).broker.capabilities
        ]
    }


@router.get("/{extension}/approval")
def approval_status(extension: str, request: Request) -> dict[str, Any]:
    return _host(request).approval_status(extension)


@router.post("/{extension}/approve")
def approve_extension(extension: str, body: dict[str, Any], request: Request) -> Any:
    return _host(request).approve(extension, str(body.get("password", "")))


@router.post("/{extension}/revoke")
def revoke_extension(extension: str, request: Request) -> dict[str, Any]:
    _host(request).revoke(extension)
    return {"ok": True}


@router.post("/inject")
def inject_event(body: dict[str, Any], request: Request) -> dict[str, Any]:
    return _host(request).inject(
        str(body.get("extension", "")),
        str(body.get("event", "")),
        dict(body.get("payload") or {}),
    )


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


@router.get("/{extension}/verify")
def verify_extension(extension: str, request: Request) -> dict[str, Any]:
    return _host(request).verify(extension)


@router.post("/{extension}/test")
def test_extension(
    extension: str,
    body: dict[str, Any],
    request: Request,
    rounds: int = Query(default=1, ge=1, le=64),
) -> Any:
    return _host(request).run_once(extension, body, rounds)


@router.post("/{extension}/command/{command}")
def run_command(
    extension: str, command: str, body: dict[str, Any], request: Request
) -> Any:
    return _host(request).invoke(extension, command, body)

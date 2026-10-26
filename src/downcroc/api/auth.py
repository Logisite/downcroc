from __future__ import annotations

import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from downcroc.runtime.config.schema import Settings

PUBLIC_API_PATH = "/api/health"
LOOPBACK_ALIASES = {
    "127.0.0.1": {"127.0.0.1", "localhost"},
    "::1": {"[::1]", "localhost"},
    "localhost": {"127.0.0.1", "[::1]", "localhost"},
}


def _authority(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _allowed_hosts(settings: Settings) -> set[str]:
    port = settings.daemon.port
    names = LOOPBACK_ALIASES.get(settings.daemon.host, {settings.daemon.host})
    return {f"{_authority(name)}:{port}" for name in names}


def _allowed_origins(hosts: set[str]) -> set[str]:
    return {f"http://{host}" for host in hosts}


def _bearer(headers: Headers, token: str) -> bool:
    if not token:
        return False
    value = headers.get("authorization")
    if value is None:
        return False
    scheme, separator, credential = value.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return False
    credential = credential.strip()
    if not credential or " " in credential:
        return False
    return secrets.compare_digest(credential, token)


def _reject(
    status: int,
    error: str,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"error": error, "message": message, "status": status},
        status_code=status,
        headers=headers,
    )


class ApiAuthMiddleware:
    def __init__(self, app: ASGIApp, *, token: str, settings: Settings) -> None:
        self.app = app
        self.token = token
        hosts = _allowed_hosts(settings)
        self.hosts = hosts
        self.origins = _allowed_origins(hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        host = (headers.get("host") or "").lower()
        if host not in self.hosts:
            response = _reject(
                403,
                "forbidden_host",
                "the Host header is not trusted",
            )
            await response(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin is not None and origin.lower() not in self.origins:
            response = _reject(
                403,
                "forbidden_origin",
                "the Origin header is not trusted",
            )
            await response(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == PUBLIC_API_PATH or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        if not _bearer(headers, self.token):
            response = _reject(
                401,
                "unauthorized",
                "a valid daemon bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class Api:
    def __init__(self, base_url: str, token_file: Path | None = None) -> None:
        self.base_url = base_url
        self.token_file = token_file
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def token(self) -> str | None:
        if self.token_file is None:
            return None
        try:
            value = self.token_file.read_text(encoding="ascii").strip()
        except OSError:
            return None
        return value or None

    def raw(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        merged = dict(headers or {})
        if data is not None:
            merged.setdefault("Content-Type", "application/json")
        if auth:
            token = self.token()
            if token is not None:
                merged["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=merged,
        )
        try:
            with self._opener.open(request, timeout=180) as response:
                payload = response.read()
                return response.status, _decode(payload)
        except urllib.error.HTTPError as error:
            return error.code, _decode(error.read())

    def get(self, path: str) -> Any:
        status, body = self.raw("GET", path)
        _raise(status, body)
        return body

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        status, payload = self.raw("POST", path, body or {})
        _raise(status, payload)
        return payload

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        status, payload = self.raw("PATCH", path, body)
        _raise(status, payload)
        return payload

    def unlock(self, password: str = "test-password") -> dict[str, Any]:
        status, payload = self.raw("POST", "/api/vault/unlock", {"password": password})
        if status == 423 and payload.get("message") == "the vault does not exist":
            return self.post("/api/vault/init", {"password": password})
        _raise(status, payload)
        return payload

    def create_account(
        self, address: str, provider: str = "generic", label: str = ""
    ) -> dict[str, Any]:
        return self.post(
            "/api/accounts",
            {"provider": provider, "address": address, "label": label},
        )

    def connect(
        self, account_id: str, password: str = "app-password"
    ) -> dict[str, Any]:
        return self.post(f"/api/accounts/{account_id}/connect", {"password": password})

    def submit(self, path: str, template: str | None = None) -> dict[str, Any]:
        return self.post("/api/batches", {"path": path, "template": template})

    def preview(
        self, path: str, template: str | None = None, key: str | None = None
    ) -> dict[str, Any]:
        suffix = "" if key is None else f"?key={urllib.parse.quote(key)}"
        return self.post(
            f"/api/batches/preview{suffix}", {"path": path, "template": template}
        )


def _decode(payload: bytes) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload.decode())
    except json.JSONDecodeError:
        return payload.decode(errors="replace")


def _raise(status: int, body: Any) -> None:
    if status >= 400:
        raise ApiError(status, body)


class ApiError(Exception):
    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"{status}: {body}")
        self.status = status
        self.body = body

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from downcroc.runtime.paths import Paths
from downcroc.runtime.service.lock import running


class CliError(RuntimeError):
    def __init__(
        self,
        message: str,
        fields: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.fields = fields or {}


@contextmanager
def api(paths: Paths) -> Iterator[httpx.Client]:
    info = running(paths.service_file)
    if info is None:
        raise CliError(
            "downcroc is not running",
            {"hint": "start it with: downcroc service start"},
        )
    with httpx.Client(
        base_url=info.base_url,
        timeout=None,
        trust_env=False,
    ) as client:
        yield client


def _body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _raise(response: httpx.Response) -> None:
    body = _body(response)
    detail = body.get("message") or response.text or f"HTTP {response.status_code}"
    code = body.get("error")
    message = f"{code}: {detail}" if code else detail
    fields = body.get("fields")
    raise CliError(
        str(message),
        fields if isinstance(fields, dict) else {},
    )


def _params(values: dict[str, Any] | None) -> dict[str, Any]:
    if not values:
        return {}
    return {key: value for key, value in values.items() if value is not None}


def call(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json: Any = None,
    params: dict[str, Any] | None = None,
) -> Any:
    try:
        response = client.request(
            method,
            path,
            json=json,
            params=_params(params),
        )
    except httpx.HTTPError as error:
        raise CliError(f"cannot reach downcroc: {error}") from error
    if response.status_code >= 400:
        _raise(response)
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise CliError("the daemon returned a non-JSON response") from error


def get(
    client: httpx.Client,
    path: str,
    **params: Any,
) -> Any:
    return call(client, "GET", path, params=params)


def post(
    client: httpx.Client,
    path: str,
    body: Any = None,
    **params: Any,
) -> Any:
    return call(client, "POST", path, json=body, params=params)


def patch(
    client: httpx.Client,
    path: str,
    body: Any,
) -> Any:
    return call(client, "PATCH", path, json=body)


def delete(client: httpx.Client, path: str) -> Any:
    return call(client, "DELETE", path)


def bytes_of(
    client: httpx.Client,
    path: str,
) -> tuple[bytes, str | None]:
    try:
        response = client.get(path)
    except httpx.HTTPError as error:
        raise CliError(f"cannot reach downcroc: {error}") from error
    if response.status_code >= 400:
        _raise(response)
    return response.content, response.headers.get("content-disposition")

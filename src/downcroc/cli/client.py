from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from downcroc.cli.errors import CliError
from downcroc.runtime.paths import Paths
from downcroc.runtime.service import token as service_token
from downcroc.runtime.service.lock import running

DEFAULT_TIMEOUT_S = 10.0

__all__ = [
    "CliError",
    "api",
    "bytes_of",
    "call",
    "delete",
    "get",
    "get_page",
    "patch",
    "post",
    "put",
    "token",
]


class _Client(httpx.Client):
    budget: float


def token(paths: Paths) -> str | None:
    return service_token.read(paths.token_file)


def _timeout(seconds: float | None) -> httpx.Timeout:
    if seconds is None or seconds <= 0:
        return httpx.Timeout(None, connect=DEFAULT_TIMEOUT_S)
    return httpx.Timeout(seconds, connect=min(seconds, DEFAULT_TIMEOUT_S))


@contextmanager
def api(paths: Paths, *, timeout: float | None = DEFAULT_TIMEOUT_S) -> Iterator[Any]:
    info = running(paths.service_file)
    if info is None:
        raise CliError(
            "downcroc is not running",
            hint="start it with: downcroc service start",
        )
    current = token(paths)
    if current is None:
        raise CliError(
            "the daemon token is missing",
            hint="restart the daemon to issue a new token",
        )
    with _Client(
        base_url=info.base_url,
        timeout=_timeout(timeout),
        trust_env=False,
        headers={"Authorization": f"Bearer {current}"},
    ) as client:
        client.budget = timeout if timeout is not None else DEFAULT_TIMEOUT_S
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
    fields = body.get("fields")
    details = body.get("details")
    raise CliError(
        str(detail),
        code=str(body.get("error")) if body.get("error") else None,
        hint=str(body["hint"]) if body.get("hint") else None,
        fields=fields if isinstance(fields, dict) else {},
        details=details if isinstance(details, (dict, list)) else None,
    )


def _params(values: dict[str, Any] | None) -> dict[str, Any]:
    if not values:
        return {}
    return {key: value for key, value in values.items() if value is not None}


def _timeout_error(client: httpx.Client, method: str, path: str) -> CliError:
    budget = getattr(client, "budget", DEFAULT_TIMEOUT_S)
    return CliError(
        f"no response after {budget:.1f}s for {method} {path}",
        code="daemon_timeout",
        hint="check `downcroc service status`, or raise --timeout",
    )


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
    except httpx.TimeoutException as error:
        raise _timeout_error(client, method, path) from error
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


def get_page(
    client: httpx.Client,
    path: str,
    **params: Any,
) -> tuple[Any, int | None]:
    try:
        response = client.get(path, params=_params(params))
    except httpx.TimeoutException as error:
        raise _timeout_error(client, "GET", path) from error
    except httpx.HTTPError as error:
        raise CliError(f"cannot reach downcroc: {error}") from error
    if response.status_code >= 400:
        _raise(response)
    total = response.headers.get("x-total-count")
    return response.json(), int(total) if total and total.isdigit() else None


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


def put(
    client: httpx.Client,
    path: str,
    body: Any,
) -> Any:
    return call(client, "PUT", path, json=body)


def delete(client: httpx.Client, path: str) -> Any:
    return call(client, "DELETE", path)


def bytes_of(
    client: httpx.Client,
    path: str,
) -> tuple[bytes, str | None]:
    try:
        response = client.get(path)
    except httpx.TimeoutException as error:
        raise _timeout_error(client, "GET", path) from error
    except httpx.HTTPError as error:
        raise CliError(f"cannot reach downcroc: {error}") from error
    if response.status_code >= 400:
        _raise(response)
    return response.content, response.headers.get("content-disposition")

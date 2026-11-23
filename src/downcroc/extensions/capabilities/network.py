from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import require
from downcroc.extensions.errors import CapabilityDenied


def register_network(broker: Broker) -> None:
    broker.register(("http.request", "provider.call"), http_request)
    broker.register(("socket.connect",), socket_connect)


def http_request(inv: Invocation, params: dict[str, Any]) -> Any:
    url = require(inv, "url")
    host = urlparse(url).hostname or ""
    _check_host(inv, host)
    headers = dict(params.get("headers") or {})
    credential = inv.param("credential")
    if credential:
        headers["Authorization"] = f"Bearer {_token(inv, str(credential))}"
    method = str(inv.param("method", "GET")).upper()
    response = httpx.request(
        method,
        url,
        headers=headers,
        json=params.get("body"),
        timeout=inv.settings.call_timeout_s,
    )
    return {"status": response.status_code, "body": _body(response)}


def _check_host(inv: Invocation, host: str) -> None:
    allowed = set()
    for grant in inv.grants:
        name, _, target = grant.partition(":")
        if name == "http.request" and target and target != "*":
            allowed.add(target)
    if (
        allowed
        and host not in allowed
        and not host.endswith(tuple(f".{item}" for item in allowed))
    ):
        raise CapabilityDenied(f"host {host} is not allowlisted")


def _token(inv: Invocation, reference: str) -> str:
    kind, _, value = reference.partition(":")
    if kind == "account":
        account = inv.services.accounts.get(value)
        spec = inv.services.providers.get(account.provider)
        return inv.services.credentials.access_token(account, spec)
    if kind == "secret":
        secret = inv.services.vault.get_secret(value)
        return str(getattr(secret, "value", ""))
    raise CapabilityDenied(f"unknown credential reference {kind}")


def _body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:4000]


def socket_connect(inv: Invocation, params: dict[str, Any]) -> Any:
    raise CapabilityDenied("socket.connect is not available")

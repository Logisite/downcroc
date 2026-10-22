from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cbor2


class SecretFormatError(Exception):
    pass


class PayloadError(Exception):
    pass


@dataclass(frozen=True)
class Secret:
    value: str
    expires_at: str | None = None
    scopes: tuple[str, ...] = ()


def encode_map(payload: dict[str, dict[str, Any]]) -> bytes:
    return cbor2.dumps(payload)


def decode_map(data: bytes) -> dict[str, dict[str, Any]]:
    try:
        payload = cbor2.loads(data)
    except cbor2.CBORDecodeError as error:
        raise PayloadError(str(error)) from error
    if not isinstance(payload, dict):
        raise PayloadError("the payload is not a map")
    if not all(
        isinstance(key, str) and isinstance(value, dict)
        for key, value in payload.items()
    ):
        raise PayloadError("the payload has a non-map entry")
    return payload


def pack(secret: Secret) -> dict[str, Any]:
    record: dict[str, Any] = {"value": secret.value}
    if secret.expires_at is not None:
        record["expires_at"] = secret.expires_at
    if secret.scopes:
        record["scopes"] = list(secret.scopes)
    return record


def unpack(record: dict[str, Any]) -> Secret:
    value = record.get("value")
    if not isinstance(value, str):
        raise SecretFormatError("secret record has no string value")
    expires_at = record.get("expires_at")
    if expires_at is not None and not isinstance(expires_at, str):
        raise SecretFormatError("secret record has a non-string expiry")
    scopes = record.get("scopes", [])
    if not isinstance(scopes, list) or not all(
        isinstance(item, str) for item in scopes
    ):
        raise SecretFormatError("secret record has invalid scopes")
    return Secret(value=value, expires_at=expires_at, scopes=tuple(scopes))

from __future__ import annotations


def sasl_string(address: str, access_token: str) -> str:
    return f"user={address}\x01auth=Bearer {access_token}\x01\x01"


def sasl_bytes(address: str, access_token: str) -> bytes:
    return sasl_string(address, access_token).encode("utf-8")

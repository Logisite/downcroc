from __future__ import annotations

import base64
import hashlib
import secrets

VERIFIER_BYTES = 64


def new_verifier() -> str:
    return secrets.token_urlsafe(VERIFIER_BYTES)


def challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

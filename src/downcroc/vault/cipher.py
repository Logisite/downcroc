from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptError(Exception):
    pass


def seal(key: bytes, header: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    return AESGCM(key).encrypt(nonce, plaintext, header)


def unseal(key: bytes, header: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, header)
    except InvalidTag as error:
        raise DecryptError("authentication failed") from error

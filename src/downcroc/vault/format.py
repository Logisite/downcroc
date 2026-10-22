from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass

MAGIC = b"DNCROC1"
VERSION = 1
KDF_ARGON2ID = 1
SALT_BYTES = 16
NONCE_BYTES = 12
DIGEST_BYTES = 32
HEADER_BYTES = len(MAGIC) + 2 + 12 + SALT_BYTES + NONCE_BYTES
FIXED_BYTES = HEADER_BYTES + DIGEST_BYTES
MEMORY_MIN_KIB = 8 * 1024
MEMORY_MAX_KIB = 1024 * 1024
ITERATIONS_MAX = 64
LANES_MAX = 32
TAG_BYTES = 16


class FileCorrupt(Exception):
    def __init__(self, offset: int, expected: str) -> None:
        super().__init__(f"byte {offset}: expected {expected}")
        self.offset = offset
        self.expected = expected


@dataclass(frozen=True)
class Header:
    memory_kib: int
    iterations: int
    lanes: int
    salt: bytes
    nonce: bytes


def header_bytes(header: Header) -> bytes:
    params = struct.pack(">III", header.memory_kib, header.iterations, header.lanes)
    return MAGIC + bytes((VERSION, KDF_ARGON2ID)) + params + header.salt + header.nonce


def encode(header: Header, ciphertext: bytes) -> bytes:
    prefix = header_bytes(header)
    digest = hashlib.sha256(prefix + ciphertext).digest()
    return prefix + digest + ciphertext


def decode(data: bytes) -> tuple[Header, bytes]:
    if len(data) < len(MAGIC):
        raise FileCorrupt(0, f"at least {len(MAGIC)} bytes")
    if data[: len(MAGIC)] != MAGIC:
        raise FileCorrupt(0, MAGIC.decode("ascii"))

    version_at = len(MAGIC)
    if len(data) < version_at + 1:
        raise FileCorrupt(version_at, f"version {VERSION}")
    if data[version_at] != VERSION:
        raise FileCorrupt(version_at, f"version {VERSION}")

    kdf_at = version_at + 1
    if len(data) < kdf_at + 1:
        raise FileCorrupt(kdf_at, f"kdf {KDF_ARGON2ID}")
    if data[kdf_at] != KDF_ARGON2ID:
        raise FileCorrupt(kdf_at, f"kdf {KDF_ARGON2ID}")

    params_at = kdf_at + 1
    if len(data) < HEADER_BYTES:
        raise FileCorrupt(len(data), f"at least {HEADER_BYTES} bytes")
    memory, iterations, lanes = struct.unpack(">III", data[params_at : params_at + 12])
    if not MEMORY_MIN_KIB <= memory <= MEMORY_MAX_KIB:
        raise FileCorrupt(params_at, f"{MEMORY_MIN_KIB}..{MEMORY_MAX_KIB} KiB")
    if not 1 <= iterations <= ITERATIONS_MAX:
        raise FileCorrupt(params_at + 4, f"1..{ITERATIONS_MAX}")
    if not 1 <= lanes <= LANES_MAX:
        raise FileCorrupt(params_at + 8, f"1..{LANES_MAX}")

    if len(data) < FIXED_BYTES:
        raise FileCorrupt(HEADER_BYTES, f"at least {DIGEST_BYTES} bytes for a digest")

    salt_at = params_at + 12
    salt = data[salt_at : salt_at + SALT_BYTES]
    nonce_at = salt_at + SALT_BYTES
    nonce = data[nonce_at : nonce_at + NONCE_BYTES]
    ciphertext = data[FIXED_BYTES:]
    if len(ciphertext) < TAG_BYTES:
        raise FileCorrupt(FIXED_BYTES, "ciphertext with an authentication tag")

    digest = hashlib.sha256(data[:HEADER_BYTES] + ciphertext).digest()
    stored = data[HEADER_BYTES:FIXED_BYTES]
    if not hmac.compare_digest(digest, stored):
        raise FileCorrupt(FIXED_BYTES, f"digest {digest.hex()[:16]}")

    header = Header(
        memory_kib=memory,
        iterations=iterations,
        lanes=lanes,
        salt=salt,
        nonce=nonce,
    )
    return header, ciphertext

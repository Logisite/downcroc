from __future__ import annotations

import time
from dataclasses import dataclass

from argon2.exceptions import HashingError
from argon2.low_level import Type, hash_secret_raw

KEY_BYTES = 32


class KdfError(Exception):
    pass


@dataclass(frozen=True)
class KdfParams:
    memory_kib: int
    iterations: int
    lanes: int


def derive(password: str, salt: bytes, params: KdfParams) -> bytes:
    try:
        return hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=params.iterations,
            memory_cost=params.memory_kib,
            parallelism=params.lanes,
            hash_len=KEY_BYTES,
            type=Type.ID,
        )
    except (HashingError, MemoryError) as error:
        raise KdfError(str(error)) from error


def tune(
    password: str,
    salt: bytes,
    params: KdfParams,
    target_ms: int,
    max_memory_kib: int,
) -> tuple[KdfParams, bytes, int]:
    memory = params.memory_kib
    best: tuple[KdfParams, bytes, int] | None = None
    while memory <= max_memory_kib:
        candidate = KdfParams(
            memory_kib=memory,
            iterations=params.iterations,
            lanes=params.lanes,
        )
        started = time.monotonic()
        try:
            key = derive(password, salt, candidate)
        except KdfError:
            if best is None:
                raise
            break
        elapsed = round((time.monotonic() - started) * 1000)
        best = (candidate, key, elapsed)
        if elapsed >= target_ms:
            break
        memory *= 2
    if best is None:
        raise KdfError("no argon2 parameters fit the memory ceiling")
    return best

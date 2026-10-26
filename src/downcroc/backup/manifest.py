from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from downcroc.domain.errors import BackupInvalid

BUNDLE_FORMAT = 1
MANIFEST_NAME = "manifest.json"
CHUNK = 1024 * 1024


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_format: int
    app_version: str
    schema_revision: str
    created_at: str
    hostname: str
    counts: dict[str, int]
    files: dict[str, str]
    bundle_hash: str
    notes: str | None = None


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def files_digest(files: Mapping[str, str]) -> str:
    payload = "".join(f"{name}:{digest}\n" for name, digest in sorted(files.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def to_bytes(manifest: Manifest) -> bytes:
    document = json.dumps(
        manifest.model_dump(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return f"{document}\n".encode()


def parse(payload: bytes) -> Manifest:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupInvalid(
            "manifest is not valid JSON",
            fields={"file": MANIFEST_NAME},
        ) from error
    try:
        return Manifest.model_validate(document)
    except ValidationError as error:
        raise BackupInvalid(
            "manifest does not match the bundle format",
            fields={"file": MANIFEST_NAME},
        ) from error

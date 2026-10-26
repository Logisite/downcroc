from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path, PurePosixPath

import zstandard

from downcroc.backup.manifest import (
    BUNDLE_FORMAT,
    MANIFEST_NAME,
    Manifest,
    files_digest,
    parse,
)
from downcroc.backup.revisions import check_revision
from downcroc.domain.errors import BackupInvalid, RestoreRefused
from downcroc.runtime.logging.setup import EventLogger

CHUNK = 1024 * 1024
MANIFEST_LIMIT = 16 * 1024 * 1024


def _safe_name(member: tarfile.TarInfo) -> str:
    name = member.name
    while name.startswith("./"):
        name = name[2:]
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BackupInvalid(
            "bundle contains an unsafe path",
            fields={"file": member.name},
        )
    return path.as_posix()


def _read_manifest(archive: tarfile.TarFile, member: tarfile.TarInfo) -> Manifest:
    stream = archive.extractfile(member)
    if stream is None:
        raise BackupInvalid(
            "manifest is not a regular file",
            fields={"file": MANIFEST_NAME},
        )
    payload = stream.read(MANIFEST_LIMIT + 1)
    if len(payload) > MANIFEST_LIMIT:
        raise BackupInvalid(
            "manifest is too large",
            fields={"file": MANIFEST_NAME},
        )
    return parse(payload)


def _digest(archive: tarfile.TarFile, member: tarfile.TarInfo) -> str:
    stream = archive.extractfile(member)
    if stream is None:
        raise BackupInvalid(
            "bundle entry is not a regular file",
            fields={"file": member.name},
        )
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def _check_files(manifest: Manifest, hashes: dict[str, str]) -> None:
    expected = set(manifest.files)
    actual = set(hashes)
    missing = sorted(expected - actual)
    if missing:
        raise BackupInvalid(
            "bundle is missing a manifest entry",
            fields={"file": missing[0]},
        )
    unlisted = sorted(actual - expected)
    if unlisted:
        raise BackupInvalid(
            "bundle contains an unlisted entry",
            fields={"file": unlisted[0]},
        )
    changed = sorted(name for name in expected if hashes[name] != manifest.files[name])
    if changed:
        raise BackupInvalid(
            "bundle entry hash does not match the manifest",
            fields={"file": changed[0]},
        )
    if manifest.bundle_hash != files_digest(manifest.files):
        raise BackupInvalid(
            "bundle hash does not match the manifest",
            fields={"file": MANIFEST_NAME},
        )


def verify_bundle(
    path: Path,
    log: EventLogger | None = None,
    check_schema: bool = True,
) -> Manifest:
    hashes: dict[str, str] = {}
    manifest: Manifest | None = None
    try:
        with path.open("rb") as raw:
            reader = zstandard.ZstdDecompressor().stream_reader(raw)
            with reader, tarfile.open(fileobj=reader, mode="r|") as archive:
                for member in archive:
                    name = _safe_name(member)
                    if member.isdir():
                        continue
                    if not member.isfile():
                        raise BackupInvalid(
                            "bundle entry is not a regular file",
                            fields={"file": name},
                        )
                    if name == MANIFEST_NAME:
                        if manifest is not None:
                            raise BackupInvalid(
                                "bundle contains more than one manifest",
                                fields={"file": name},
                            )
                        manifest = _read_manifest(archive, member)
                        continue
                    if name in hashes:
                        raise BackupInvalid(
                            "bundle contains a duplicate entry",
                            fields={"file": name},
                        )
                    hashes[name] = _digest(archive, member)
    except BackupInvalid as error:
        if log is not None:
            log.warning(
                "backup.verify_failed",
                file=(error.fields or {}).get("file", "bundle"),
            )
        raise
    except (OSError, EOFError, tarfile.TarError, zstandard.ZstdError) as error:
        if log is not None:
            log.warning("backup.verify_failed", file=path.name)
        raise BackupInvalid(
            "bundle cannot be read",
            fields={"file": path.name},
        ) from error

    try:
        if manifest is None:
            raise BackupInvalid(
                "bundle has no manifest",
                fields={"file": MANIFEST_NAME},
            )
        if manifest.bundle_format != BUNDLE_FORMAT:
            raise RestoreRefused(
                "bundle format is not supported by this build",
                fields={
                    "revision": str(manifest.bundle_format),
                    "current": str(BUNDLE_FORMAT),
                    "reason": "unsupported bundle format",
                },
            )
        _check_files(manifest, hashes)
        if check_schema:
            check_revision(manifest.schema_revision)
    except BackupInvalid as error:
        if log is not None:
            log.warning(
                "backup.verify_failed",
                file=(error.fields or {}).get("file", "bundle"),
            )
        raise

    if log is not None:
        log.info("backup.verified", files=len(hashes), ok=True)
    return manifest

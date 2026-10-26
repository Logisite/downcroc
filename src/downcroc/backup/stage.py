from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import zstandard

from downcroc.backup.db_snapshot import (
    count_mismatches,
    foreign_key_problems,
    integrity_problems,
    missing_content,
    schema_revision,
    table_counts,
)
from downcroc.backup.manifest import MANIFEST_NAME, Manifest
from downcroc.domain.errors import RestoreFailed
from downcroc.runtime.paths import Paths

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Stage:
    data: Path
    config: Path
    files: int
    counts: dict[str, int]


def new_stage(paths: Paths) -> tuple[Path, Path]:
    token = secrets.token_hex(8)
    data = paths.data.parent / f".downcroc-restore-{token}-data"
    config = paths.config.parent / f".downcroc-restore-{token}-config"
    data.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    data.mkdir(mode=0o700)
    config.mkdir(mode=0o700)
    return data, config


def discard_stage(data: Path | None, config: Path | None) -> None:
    if data is not None:
        shutil.rmtree(data, ignore_errors=True)
    if config is not None:
        shutil.rmtree(config, ignore_errors=True)


def _safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RestoreFailed(
            "bundle contains an unsafe path",
            fields={"file": name},
        )
    return path


def _destination(
    name: str,
    data: Path,
    config: Path,
) -> tuple[Path, str]:
    relative = _safe_relative(name)
    if name == "db/downcroc.db":
        return data / "downcroc.db", name
    if name.startswith("content/"):
        return data / relative, name
    if name in ("vault.enc", "failed.jsonl"):
        return data / name, name
    if name.startswith("logs/"):
        return data / relative, name
    if name.startswith("config/"):
        inner = PurePosixPath(*relative.parts[1:])
        if not inner.parts:
            raise RestoreFailed(
                "bundle config entry has no path", fields={"file": name}
            )
        return config / inner, name
    raise RestoreFailed("bundle contains an unknown entry", fields={"file": name})


def _write(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    destination: Path,
) -> str:
    stream = archive.extractfile(member)
    if stream is None:
        raise RestoreFailed(
            "bundle entry is not a regular file",
            fields={"file": member.name},
        )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    handle = os.open(
        destination,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600,
    )
    digest = hashlib.sha256()
    try:
        with os.fdopen(handle, "wb") as target:
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def stage_bundle(bundle: Path, manifest: Manifest, paths: Paths) -> Stage:
    data, config = new_stage(paths)
    hashes: dict[str, str] = {}
    try:
        try:
            with bundle.open("rb") as raw:
                reader = zstandard.ZstdDecompressor().stream_reader(raw)
                with reader, tarfile.open(fileobj=reader, mode="r|") as archive:
                    for member in archive:
                        if member.isdir():
                            continue
                        if not member.isfile():
                            raise RestoreFailed(
                                "bundle entry is not a regular file",
                                fields={"file": member.name},
                            )
                        name = member.name
                        while name.startswith("./"):
                            name = name[2:]
                        if name == MANIFEST_NAME:
                            continue
                        destination, key = _destination(name, data, config)
                        if key in hashes:
                            raise RestoreFailed(
                                "bundle contains a duplicate entry",
                                fields={"file": key},
                            )
                        hashes[key] = _write(archive, member, destination)
        except RestoreFailed:
            raise
        except (OSError, EOFError, tarfile.TarError, zstandard.ZstdError) as error:
            raise RestoreFailed(
                "bundle cannot be staged",
                fields={"file": bundle.name},
            ) from error

        _check_hashes(manifest, hashes)
        database = data / "downcroc.db"
        if not database.is_file():
            raise RestoreFailed(
                "bundle has no database",
                fields={"file": "db/downcroc.db"},
            )
        _check_database(database, data / "content", manifest)
        counts = table_counts(database)
        return Stage(data=data, config=config, files=len(hashes), counts=counts)
    except BaseException:
        discard_stage(data, config)
        raise


def _check_hashes(manifest: Manifest, hashes: dict[str, str]) -> None:
    expected = set(manifest.files)
    actual = set(hashes)
    missing = sorted(expected - actual)
    if missing:
        raise RestoreFailed(
            "bundle is missing a manifest entry",
            fields={"file": missing[0]},
        )
    unlisted = sorted(actual - expected)
    if unlisted:
        raise RestoreFailed(
            "bundle contains an unlisted entry",
            fields={"file": unlisted[0]},
        )
    changed = sorted(name for name in expected if hashes[name] != manifest.files[name])
    if changed:
        raise RestoreFailed(
            "bundle entry hash does not match the manifest",
            fields={"file": changed[0]},
        )


def _check_database(database: Path, content: Path, manifest: Manifest) -> None:
    problems = integrity_problems(database)
    if problems:
        raise RestoreFailed(
            "database integrity check failed",
            fields={"file": "db/downcroc.db", "reason": problems[0]},
        )
    violations = foreign_key_problems(database)
    if violations:
        raise RestoreFailed(
            "database foreign key check failed",
            fields={"file": "db/downcroc.db", "reason": violations[0]},
        )
    revision = schema_revision(database)
    if revision != manifest.schema_revision:
        raise RestoreFailed(
            "database revision does not match the manifest",
            fields={
                "file": "db/downcroc.db",
                "reason": f"{revision or 'none'} != {manifest.schema_revision}",
            },
        )
    actual = table_counts(database)
    mismatched = count_mismatches(manifest.counts, actual)
    if mismatched:
        table = mismatched[0]
        raise RestoreFailed(
            "database counts do not match the manifest",
            fields={
                "table": table,
                "reason": f"{manifest.counts[table]} != {actual.get(table, 0)}",
            },
        )
    missing = missing_content(database, content)
    if missing:
        raise RestoreFailed(
            "bundle is missing referenced content",
            fields={"file": f"content/{missing[0]}"},
        )

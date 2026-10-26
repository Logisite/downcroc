from __future__ import annotations

import io
import os
import shutil
import socket
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import zstandard

from downcroc.backup.db_snapshot import schema_revision, snapshot_database, table_counts
from downcroc.backup.fsops import sync_dir
from downcroc.backup.manifest import (
    BUNDLE_FORMAT,
    MANIFEST_NAME,
    Manifest,
    file_digest,
    files_digest,
    to_bytes,
)
from downcroc.backup.verify import verify_bundle
from downcroc.core.maintenance import MAINTENANCE
from downcroc.domain.errors import BackupFailed, BackupInvalid, RestoreRefused
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths
from downcroc.version import __version__

CHUNK = 1024 * 1024
COMPRESSION_LEVEL = 3


@dataclass(frozen=True)
class BackupResult:
    path: Path
    files: int
    bytes: int
    duration_ms: int
    manifest: Manifest


class BackupService:
    def __init__(self, paths: Paths, log: EventLogger) -> None:
        self._paths = paths
        self._log = log

    def create(self, target: Path, include_logs: bool = False) -> BackupResult:
        destination = target.expanduser().absolute()
        if destination.is_dir():
            raise BackupFailed(
                "backup path is a directory",
                fields={"path": str(destination)},
            )
        for root in (self._paths.data, self._paths.config):
            if destination.is_relative_to(root):
                raise BackupFailed(
                    "write the bundle outside the data and config directories",
                    fields={"path": str(destination)},
                )
        source = self._paths.data / "downcroc.db"
        if not source.is_file():
            raise BackupFailed(
                "database does not exist",
                fields={"path": str(source)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        work = Path(
            tempfile.mkdtemp(
                prefix=".downcroc-backup-",
                dir=destination.parent,
            )
        )
        partial = destination.with_name(f"{destination.name}.partial")
        started = time.monotonic()
        try:
            with MAINTENANCE:
                snapshot = work / "downcroc.db"
                snapshot_database(source, snapshot)
                revision = schema_revision(snapshot)
                if revision is None:
                    raise BackupFailed("database has no schema revision")
                counts = table_counts(snapshot)
                entries = self._entries(snapshot, include_logs)
                entries = self._freeze(work, entries)
                files = {name: file_digest(path) for name, path in entries}
                manifest = Manifest(
                    bundle_format=BUNDLE_FORMAT,
                    app_version=__version__,
                    schema_revision=revision,
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                    hostname=socket.gethostname(),
                    counts=counts,
                    files=files,
                    bundle_hash=files_digest(files),
                )
                self._write(partial, entries, manifest)
            try:
                verify_bundle(partial, self._log)
            except (BackupInvalid, RestoreRefused) as error:
                raise BackupFailed(
                    f"backup verification failed: {error}",
                    fields={"path": str(destination)},
                ) from error
            os.chmod(partial, 0o600)
            os.replace(partial, destination)
            sync_dir(destination.parent)
            duration = round((time.monotonic() - started) * 1000)
            size = destination.stat().st_size
            self._log.info(
                "backup.created",
                path=str(destination),
                files=len(files),
                bytes=size,
                duration_ms=duration,
            )
            return BackupResult(
                path=destination,
                files=len(files),
                bytes=size,
                duration_ms=duration,
                manifest=manifest,
            )
        except BackupFailed:
            raise
        except (OSError, tarfile.TarError, zstandard.ZstdError) as error:
            raise BackupFailed(
                "backup could not be written",
                fields={"path": str(destination)},
            ) from error
        finally:
            partial.unlink(missing_ok=True)
            shutil.rmtree(work, ignore_errors=True)

    def _entries(self, snapshot: Path, include_logs: bool) -> list[tuple[str, Path]]:
        entries: list[tuple[str, Path]] = [("db/downcroc.db", snapshot)]
        entries.extend(self._tree(self._paths.data / "content", "content"))
        entries.extend(self._tree(self._paths.config, "config"))
        for name in ("vault.enc", "failed.jsonl"):
            path = self._paths.data / name
            if path.is_file() and not path.is_symlink():
                entries.append((name, path))
        if include_logs:
            entries.extend(self._tree(self._paths.data / "logs", "logs"))
        return entries

    def _tree(self, root: Path, prefix: str) -> list[tuple[str, Path]]:
        if not root.is_dir():
            return []
        found: list[tuple[str, Path]] = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            found.append((f"{prefix}/{relative}", path))
        return found

    def _freeze(
        self, work: Path, entries: list[tuple[str, Path]]
    ) -> list[tuple[str, Path]]:
        frozen: list[tuple[str, Path]] = []
        for name, path in entries:
            if name.startswith(("content/", "db/")):
                frozen.append((name, path))
                continue
            target = work / "files" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            target.chmod(0o600)
            frozen.append((name, target))
        return frozen

    def _write(
        self,
        target: Path,
        entries: list[tuple[str, Path]],
        manifest: Manifest,
    ) -> None:
        with target.open("wb") as raw:
            compressor = zstandard.ZstdCompressor(level=COMPRESSION_LEVEL)
            with (
                compressor.stream_writer(raw, closefd=False) as writer,
                tarfile.open(fileobj=writer, mode="w|") as archive,
            ):
                payload = to_bytes(manifest)
                self._add(archive, MANIFEST_NAME, payload)
                for name, path in entries:
                    info = archive.gettarinfo(str(path), arcname=name)
                    info.mode = 0o600
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
            raw.flush()
            os.fsync(raw.fileno())
        target.chmod(0o600)

    def _add(self, archive: tarfile.TarFile, name: str, payload: bytes) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        info.mode = 0o600
        info.mtime = int(time.time())
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        archive.addfile(info, io.BytesIO(payload))

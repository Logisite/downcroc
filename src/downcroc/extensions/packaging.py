from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tomllib
import zipapp
import zipfile
from pathlib import Path

from downcroc.extensions.errors import ManifestError
from downcroc.extensions.manifest import Manifest, parse_manifest_data

MANIFEST_NAME = "downcroc-extension.toml"


def build(source: Path, output: Path | None = None) -> tuple[Path, str]:
    if not source.is_dir():
        raise ManifestError(f"not a directory: {source}")
    manifest_path = source / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ManifestError(f"missing {MANIFEST_NAME}")
    if not (source / "__main__.py").is_file():
        raise ManifestError("missing __main__.py")
    with manifest_path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ManifestError("artifact manifest must be a table")
    data["kind"] = "pyz"
    manifest = parse_manifest_data(data, manifest_path, require_artifact=False)
    target = output or Path.cwd() / f"{manifest.id}-{manifest.version or '0'}.pyz"
    target.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(source, target, interpreter="/usr/bin/env python3")
    return target, sha256(target)


def parse_manifest(path: Path) -> Manifest:
    with path.open("rb") as handle:
        return parse_manifest_data(tomllib.load(handle), path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_artifact(path: Path) -> Manifest:
    try:
        with zipfile.ZipFile(path) as archive:
            payload = archive.read(MANIFEST_NAME)
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ManifestError(f"not a valid extension artifact: {error}") from error
    try:
        data = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ManifestError(f"invalid artifact manifest: {error}") from error
    if not isinstance(data, dict):
        raise ManifestError("artifact manifest must be a table")
    data["kind"] = "pyz"
    return parse_manifest_data(data, Path(path.name), require_artifact=False)


def install(path: Path, config_dir: Path) -> Manifest:
    artifact = read_artifact(path)
    checksum = sha256(path)
    artifacts = config_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    target = artifacts / f"{artifact.id}-{artifact.version or '0'}.pyz"
    shutil.copyfile(path, target)
    installed = Manifest(
        id=artifact.id,
        run=(),
        name=artifact.name,
        version=artifact.version,
        events=artifact.events,
        capabilities=artifact.capabilities,
        commands=artifact.commands,
        source=config_dir / f"{artifact.id}.toml",
        kind="pyz",
        artifact=str(target.relative_to(config_dir)),
        artifact_sha256=checksum,
    )
    installed.source.write_text(render_manifest(installed), encoding="utf-8")
    return installed


def artifact_path(manifest: Manifest, config_dir: Path) -> Path:
    candidate = Path(manifest.artifact)
    return candidate if candidate.is_absolute() else config_dir / candidate


def verify(manifest: Manifest, config_dir: Path) -> bool:
    if manifest.kind != "pyz" or not manifest.artifact_sha256:
        return False
    path = artifact_path(manifest, config_dir)
    return path.is_file() and sha256(path) == manifest.artifact_sha256


def command(manifest: Manifest, config_dir: Path) -> tuple[str, ...]:
    return (sys.executable, str(artifact_path(manifest, config_dir)))


def render_manifest(manifest: Manifest) -> str:
    lines = [
        f"id = {_text(manifest.id)}",
        f"name = {_text(manifest.name)}",
        f"version = {_text(manifest.version)}",
        'kind = "pyz"',
        f"artifact = {_text(manifest.artifact)}",
        f"artifact_sha256 = {_text(manifest.artifact_sha256)}",
        f"events = {_list(manifest.events)}",
        f"capabilities = {_list(manifest.capabilities)}",
    ]
    if manifest.commands:
        lines.append("")
        lines.append("[[commands]]")
        for item in manifest.commands:
            lines.append(f"name = {_text(item.name)}")
            lines.append(f"help = {_text(item.help)}")
            lines.append(f"args = {_list(item.args)}")
            lines.append("")
            lines.append("[[commands]]")
        lines.pop()
    return "\n".join(lines) + "\n"


def _list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_text(value) for value in values) + "]"


def _text(value: str) -> str:
    return json.dumps(value)

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from downcroc.extensions.errors import ManifestError

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class CommandSpec:
    name: str
    help: str = ""
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    id: str
    run: tuple[str, ...]
    name: str = ""
    version: str = ""
    events: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    commands: tuple[CommandSpec, ...] = ()
    source: Path = Path()
    kind: str = "local"
    artifact: str = ""
    artifact_sha256: str = ""

    @property
    def config_key(self) -> str:
        return self.id.replace("-", "_")


def load_manifests(directory: Path) -> list[Manifest]:
    if not directory.is_dir():
        return []
    found: list[Manifest] = []
    for path in sorted(directory.glob("*.toml")):
        found.append(parse_manifest(path))
    return found


def parse_manifest(path: Path) -> Manifest:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError) as error:
        raise ManifestError(f"cannot read {path.name}: {error}") from error
    return parse_manifest_data(data, path)


def parse_manifest_data(
    data: object, source: Path, *, require_artifact: bool = True
) -> Manifest:
    name = source.name
    if not isinstance(data, dict):
        raise ManifestError(f"{name}: manifest must be a table")
    identifier = str(data.get("id") or source.stem)
    if not _ID.fullmatch(identifier):
        raise ManifestError(f"{name}: invalid extension id {identifier}")
    kind = str(data.get("kind") or "local")
    artifact = str(data.get("artifact") or "")
    checksum = str(data.get("artifact_sha256") or "")
    run = _run(data.get("run"), name, required=kind != "pyz")
    if require_artifact and kind == "pyz" and (not artifact or not checksum):
        raise ManifestError(f"{name}: pyz extension needs artifact and artifact_sha256")
    return Manifest(
        id=identifier,
        run=run,
        name=str(data.get("name") or identifier),
        version=str(data.get("version") or ""),
        events=_strings(data.get("events"), name),
        capabilities=_strings(data.get("capabilities"), name),
        commands=_commands(data.get("commands"), name),
        source=source,
        kind=kind,
        artifact=artifact,
        artifact_sha256=checksum,
    )


def _run(value: object, source: str, *, required: bool) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) for item in value)
    ):
        raise ManifestError(f"{source}: run must be a non-empty string list")
    return tuple(value)


def _commands(value: object, source: str) -> tuple[CommandSpec, ...]:
    if not isinstance(value, list):
        return ()
    result: list[CommandSpec] = []
    for item in value:
        if not isinstance(item, dict):
            raise ManifestError(f"{source}: command must be a table")
        name = str(item.get("name") or "")
        if not _ID.fullmatch(name):
            raise ManifestError(f"{source}: invalid command name {name}")
        args = item.get("args") or []
        result.append(
            CommandSpec(
                name=name,
                help=str(item.get("help") or ""),
                args=_strings(args, source),
            )
        )
    return tuple(result)


def _strings(value: object, source: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError(f"{source}: expected a string list")
    return tuple(value)

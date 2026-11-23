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
    if not isinstance(data, dict):
        raise ManifestError(f"{path.name}: manifest must be a table")
    identifier = str(data.get("id") or path.stem)
    if not _ID.fullmatch(identifier):
        raise ManifestError(f"{path.name}: invalid extension id {identifier}")
    run = data.get("run")
    if (
        not isinstance(run, list)
        or not run
        or not all(isinstance(item, str) for item in run)
    ):
        raise ManifestError(f"{path.name}: run must be a non-empty string list")
    commands = _commands(data.get("commands"), path.name)
    return Manifest(
        id=identifier,
        run=tuple(str(item) for item in run),
        name=str(data.get("name") or identifier),
        version=str(data.get("version") or ""),
        events=_strings(data.get("events"), path.name),
        capabilities=_strings(data.get("capabilities"), path.name),
        commands=commands,
        source=path,
    )


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

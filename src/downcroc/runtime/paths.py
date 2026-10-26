from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from downcroc.runtime.fs import restrict

APP = "downcroc"


@dataclass(frozen=True)
class Paths:
    config: Path
    data: Path
    state: Path

    @property
    def config_file(self) -> Path:
        return self.config / "config.toml"

    @property
    def templates(self) -> Path:
        return self.config / "templates"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs / "downcroc.jsonl"

    @property
    def service_file(self) -> Path:
        return self.state / "service.json"

    @property
    def token_file(self) -> Path:
        return self.state / "daemon.token"

    @property
    def lock_file(self) -> Path:
        return self.state / "daemon.lock"

    @property
    def restore_marker(self) -> Path:
        return self.state / "restore.pending"


def _home(values: Mapping[str, str]) -> Path:
    return Path(
        values.get("HOME") or values.get("USERPROFILE") or os.path.expanduser("~")
    )


def _root(values: Mapping[str, str], name: str) -> Path | None:
    value = values.get(name)
    return Path(value) if value else None


def _xdg(root: Path | None, fallback: Path) -> Path:
    return root / APP if root is not None else fallback


def resolve(env: Mapping[str, str] | None = None) -> Paths:
    values = os.environ if env is None else env
    home = _home(values)
    xdg_config = _root(values, "XDG_CONFIG_HOME")
    xdg_data = _root(values, "XDG_DATA_HOME")
    xdg_state = _root(values, "XDG_STATE_HOME")
    if sys.platform == "win32":
        roaming = Path(values.get("APPDATA") or home / "AppData" / "Roaming")
        local = Path(values.get("LOCALAPPDATA") or home / "AppData" / "Local")
        config = _xdg(xdg_config, roaming / APP)
        data = _xdg(xdg_data, local / APP)
        state = _xdg(xdg_state, local / APP / "state")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support" / APP
        config = _xdg(xdg_config, base / "config")
        data = _xdg(xdg_data, base / "data")
        state = _xdg(xdg_state, base / "state")
    else:
        config = _xdg(xdg_config, home / ".config" / APP)
        data = _xdg(xdg_data, home / ".local" / "share" / APP)
        state = _xdg(xdg_state, home / ".local" / "state" / APP)
    return Paths(config, data, state)


def ensure(paths: Paths) -> None:
    for directory in (paths.config, paths.data, paths.state, paths.logs):
        directory.mkdir(parents=True, exist_ok=True)
        restrict(directory, 0o700)

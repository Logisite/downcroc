from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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
    def lock_file(self) -> Path:
        return self.state / "daemon.lock"

    @property
    def restore_marker(self) -> Path:
        return self.state / "restore.pending"


def resolve(env: Mapping[str, str] | None = None) -> Paths:
    values = os.environ if env is None else env
    home = Path(values.get("HOME") or Path.home())
    config = Path(values.get("XDG_CONFIG_HOME") or home / ".config")
    data = Path(values.get("XDG_DATA_HOME") or home / ".local" / "share")
    state = Path(values.get("XDG_STATE_HOME") or home / ".local" / "state")
    return Paths(config / APP, data / APP, state / APP)


def ensure(paths: Paths) -> None:
    for directory in (paths.config, paths.data, paths.state, paths.logs):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)

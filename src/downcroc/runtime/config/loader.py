from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from downcroc.runtime.config.schema import Settings
from downcroc.runtime.fs import restrict


class ConfigError(Exception):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def read(path: Path) -> Settings:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from error
    try:
        return Settings.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"])
        raise ConfigError(first["msg"], field=field) from error


def load_or_create(path: Path) -> tuple[Settings, bool]:
    if path.exists():
        return read(path), False
    settings = Settings()
    write(path, settings)
    return settings, True


def write(path: Path, settings: Settings) -> None:
    data = tomli_w.dumps(settings.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".config-", suffix=".toml"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        restrict(Path(temporary), 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise

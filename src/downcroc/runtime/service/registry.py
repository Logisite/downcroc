from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from downcroc.runtime.fs import restrict


@dataclass(frozen=True)
class ServiceInfo:
    pid: int
    host: str
    port: int
    started_at: str
    version: str
    api_version: str

    @property
    def base_url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"


def read(path: Path) -> ServiceInfo | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ServiceInfo(**raw)
    except OSError, ValueError, TypeError:
        return None


def write(path: Path, info: ServiceInfo) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".service-", suffix=".json"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(asdict(info), stream)
            stream.flush()
            os.fsync(stream.fileno())
        restrict(Path(temporary), 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def remove(path: Path) -> None:
    path.unlink(missing_ok=True)

from __future__ import annotations

import sys
from pathlib import Path


def install_prefix() -> Path | None:
    venv = Path(sys.prefix).resolve()
    if (
        venv.name == "venv"
        and venv.parent.name == "downcroc"
        and venv.parent.parent.name == "share"
    ):
        return venv.parent.parent.parent
    if venv.name == "venv":
        return venv.parent
    return None


def launchers(prefix: Path) -> list[Path]:
    return [prefix / "bin" / "downcroc", prefix / "bin" / "downcroc.cmd"]


def trees(prefix: Path) -> list[Path]:
    return [prefix / "share" / "downcroc", prefix / "venv"]

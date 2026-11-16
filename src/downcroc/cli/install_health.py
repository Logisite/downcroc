from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from downcroc.cli.install_layout import install_prefix

OK = "ok"
RELINKED = "relinked"
NEEDS_RELINK = "needs_relink"
NEEDS_REINSTALL = "needs_reinstall"
UNRECOVERABLE = "unrecoverable"


@dataclass(frozen=True)
class InstallHealth:
    status: str
    detail: str
    venv: Path | None = None
    base_python: Path | None = None
    fix: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (OK, RELINKED)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ok": self.ok,
            "detail": self.detail,
            "venv": str(self.venv) if self.venv else None,
            "base_python": str(self.base_python) if self.base_python else None,
            "fix": self.fix,
        }


def managed_venv() -> Path | None:
    prefix = install_prefix()
    if prefix is None:
        return None
    for candidate in (prefix / "share" / "downcroc" / "venv", prefix / "venv"):
        if (candidate / "pyvenv.cfg").is_file():
            return candidate
    return None


def _read_cfg(venv: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    for line in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator:
            cfg[name.strip().lower()] = value.strip()
    return cfg


def _version_pair(cfg: dict[str, str]) -> str:
    raw = cfg.get("version_info") or cfg.get("version") or ""
    parts = raw.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return ""


def _executable(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        found = shutil.which(str(candidate))
        candidate = Path(found) if found else candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError, RuntimeError:
        return None
    return resolved if resolved.is_file() and os.access(resolved, os.X_OK) else None


def _base_python(cfg: dict[str, str]) -> Path | None:
    candidates: list[str | Path] = []
    for key in ("base-executable", "executable"):
        if cfg.get(key):
            candidates.append(cfg[key])
    home = cfg.get("home")
    version = _version_pair(cfg)
    if home:
        candidates.extend((Path(home) / f"python{version}", Path(home) / "python3"))
    if version:
        candidates.append(f"python{version}")
    candidates.extend(("python3", "python"))
    for candidate in candidates:
        found = _executable(candidate)
        if found is not None:
            return found
    return None


def _link_names(cfg: dict[str, str]) -> tuple[str, ...]:
    names = ["python", "python3"]
    version = _version_pair(cfg)
    if version:
        names.append(f"python{version}")
    return tuple(dict.fromkeys(names))


def _bin(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _links_ok(venv: Path, cfg: dict[str, str]) -> bool:
    if os.name == "nt":
        return True
    return all(_executable(_bin(venv) / name) is not None for name in _link_names(cfg))


def _console_script_ok(venv: Path) -> bool:
    script = _bin(venv) / ("downcroc.cmd" if os.name == "nt" else "downcroc")
    if not script.is_file():
        return False
    if os.name == "nt":
        return True
    try:
        first = script.open(encoding="utf-8").readline().strip()
    except OSError:
        return False
    if not first.startswith("#!"):
        return False
    return _executable(first[2:].strip()) is not None


def _import_ok(venv: Path) -> bool:
    python = _bin(venv) / ("python.exe" if os.name == "nt" else "python")
    # Do not resolve the link to its target: the venv's site-packages only
    # come into play when the interpreter is launched through the venv path.
    if not python.is_file() or not os.access(python, os.X_OK):
        return False
    try:
        result = subprocess.run(
            [str(python), "-c", "import downcroc; import downcroc.cli.main"],
            capture_output=True,
            check=False,
            timeout=15,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


def probe() -> InstallHealth:
    venv = managed_venv()
    if venv is None:
        return InstallHealth(
            UNRECOVERABLE,
            "not a managed install",
            fix="use scripts/install.sh or scripts/install.ps1",
        )
    if not (venv / "pyvenv.cfg").is_file():
        return InstallHealth(
            NEEDS_REINSTALL,
            f"missing pyvenv.cfg in {venv}",
            venv=venv,
            fix="reinstall downcroc",
        )
    cfg = _read_cfg(venv)
    base = _base_python(cfg)
    if base is None:
        return InstallHealth(
            UNRECOVERABLE,
            f"no usable Python {_version_pair(cfg) or '3.14+'} interpreter found",
            venv=venv,
            fix="install a supported Python, then reinstall downcroc",
        )
    if not _links_ok(venv, cfg) or not _console_script_ok(venv):
        return InstallHealth(
            NEEDS_RELINK,
            f"interpreter links are broken in {_bin(venv)}",
            venv=venv,
            base_python=base,
            fix="run downcroc repair",
        )
    if not _import_ok(venv):
        return InstallHealth(
            NEEDS_REINSTALL,
            "the venv python cannot import downcroc",
            venv=venv,
            base_python=base,
            fix="run downcroc update --force, or reinstall downcroc",
        )
    return InstallHealth(
        OK,
        f"healthy; base interpreter {base}",
        venv=venv,
        base_python=base,
    )


def _normalize_links(venv: Path, cfg: dict[str, str], base: Path) -> None:
    if os.name == "nt":
        return
    binary = _bin(venv)
    binary.mkdir(parents=True, exist_ok=True)
    for name in _link_names(cfg):
        link = binary / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(base)


def repair() -> InstallHealth:
    health = probe()
    if health.ok or health.status == UNRECOVERABLE:
        return health
    if health.venv is None or health.base_python is None:
        return health
    if health.status == NEEDS_RELINK:
        cfg = _read_cfg(health.venv)
        _normalize_links(health.venv, cfg, health.base_python)
        health = probe()
        if health.ok:
            return InstallHealth(
                RELINKED,
                f"relinked the venv interpreter to {health.base_python}",
                venv=health.venv,
                base_python=health.base_python,
            )
    return health

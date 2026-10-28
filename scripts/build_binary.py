from __future__ import annotations

import argparse
import importlib.util
import platform
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "src" / "downcroc" / "cli" / "main.py"
SPEC = ROOT / "downcroc.spec"
LEGAL = ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md")


def _require(module: str, group: str) -> None:
    if importlib.util.find_spec(module) is None:
        raise SystemExit(f"{module} is not installed; run: uv sync --group {group}")


def _executable() -> str:
    return "downcroc.exe" if platform.system() == "Windows" else "downcroc"


def pyinstaller(out: Path) -> list[str]:
    _require("PyInstaller", "build")
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(out),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        str(SPEC),
    ]


def nuitka(out: Path) -> list[str]:
    _require("nuitka", "build")
    args = [
        sys.executable,
        "-m",
        "nuitka",
        "--assume-yes-for-downloads",
        "--standalone",
        "--include-package=downcroc",
        "--include-package=uvicorn",
        "--include-package-data=downcroc",
        "--include-distribution-metadata=downcroc",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=tests",
        f"--output-dir={out}",
        f"--output-filename={_executable()}",
    ]
    for name in LEGAL:
        args.append(f"--include-data-files={ROOT / name}={name}")
    migrations = ROOT / "src" / "downcroc" / "store" / "db" / "migrations"
    args.append(f"--include-data-dir={migrations}=downcroc/store/db/migrations")
    if platform.system() == "Windows":
        args.append("--windows-console-mode=force")
    args.append(str(ENTRY))
    return args


def artifact(out: Path) -> Path | None:
    name = _executable()
    matches = sorted(path for path in out.rglob(name) if path.is_file())
    return matches[0] if matches else None


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the downcroc onedir artifact with one freezer.",
    )
    parser.add_argument("tool", choices=("pyinstaller", "nuitka"))
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory, default dist/<tool>",
    )
    return parser.parse_args()


def _display(argv: list[str]) -> str:
    if platform.system() == "Windows":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def main() -> int:
    options = parse()
    out = (options.out or ROOT / "dist" / options.tool).resolve()
    out.mkdir(parents=True, exist_ok=True)
    argv = pyinstaller(out) if options.tool == "pyinstaller" else nuitka(out)
    print(_display(argv))
    code = subprocess.run(argv, cwd=ROOT, check=False).returncode
    if code != 0:
        return code
    found = artifact(out)
    if found is None:
        print(f"artifact: no {_executable()} under {out}", file=sys.stderr)
        return 1
    print(f"artifact: {found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

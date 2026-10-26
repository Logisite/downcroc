from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import closing
from importlib import metadata
from pathlib import Path


def _fail(message: str) -> None:
    print(f"wheel smoke: {message}", file=sys.stderr)
    raise SystemExit(1)


def _run(command: list[str], env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        _fail(
            f"{' '.join(command)} failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout.strip()


def _basenames(names: list[str], filename: str) -> list[str]:
    return [name for name in names if name.rsplit("/", 1)[-1] == filename]


def _wheel_names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return archive.namelist()


def _sdist_names(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as archive:
        return archive.getnames()


def _check_required(names: list[str], label: str) -> None:
    for filename in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        if not _basenames(names, filename):
            _fail(f"{label} is missing {filename}")
    for suffix in (
        "downcroc/providers/declarations/gmail.toml",
        "downcroc/providers/declarations/generic.toml",
        "downcroc/store/db/migrations/env.py",
        "downcroc/store/db/migrations/versions/270c3f4beeb9_initial_schema.py",
    ):
        if not any(name.endswith(suffix) for name in names):
            _fail(f"{label} is missing {suffix}")


def _check_artifacts(dist: Path) -> None:
    wheels = sorted(dist.glob("downcroc-*.whl"))
    sdists = sorted(dist.glob("downcroc-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        _fail(f"expected one wheel and one sdist in {dist}")
    _check_required(_wheel_names(wheels[0]), "wheel")
    _check_required(_sdist_names(sdists[0]), "source distribution")


def _check_metadata() -> str:
    distribution = metadata.distribution("downcroc")
    expected = distribution.metadata.get("License-Expression")
    if expected != "Apache-2.0":
        _fail(f"wheel metadata licence is {expected!r}")
    entry_points = {
        entry.name
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    if "downcroc" not in entry_points:
        _fail("wheel metadata has no downcroc console script")
    files = {str(item) for item in (distribution.files or [])}
    for filename in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        if not any(path.rsplit("/", 1)[-1] == filename for path in files):
            _fail(f"installed metadata is missing {filename}")
    return distribution.version


def _check_version(executable: str, expected: str) -> None:
    actual = _run([executable, "--version"])
    if actual != f"downcroc {expected}":
        _fail(f"downcroc --version returned {actual!r}, expected {expected!r}")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _health(port: int, timeout: float = 90.0) -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with opener.open(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ) as response:
                if response.status == 200:
                    return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = error
        time.sleep(0.1)
    _fail(f"daemon did not become healthy: {last}")


def _environment(root: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
    }


def _check_database(path: Path) -> None:
    if not path.is_file():
        _fail(f"daemon did not create {path}")
    with closing(sqlite3.connect(path)) as connection:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version LIMIT 1"
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    if revision is None:
        _fail("database has no Alembic revision")
    for table in ("accounts", "messages", "jobs"):
        if table not in tables:
            _fail(f"database is missing the {table} table")


def _smoke_daemon(executable: str, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="downcroc-wheel-") as temporary:
        root = Path(temporary)
        port = _free_port()
        environment = _environment(root)
        config = root / "config" / "downcroc" / "config.toml"
        config.parent.mkdir(parents=True)
        config.write_text(
            f"[daemon]\nport = {port}\nstart_timeout_s = 90.0\n",
            encoding="utf-8",
        )
        try:
            _run([executable, "service", "start"], env=environment)
            health = _health(port)
            if health.get("version") != expected:
                _fail(f"health reported version {health.get('version')!r}")
            if health.get("status") != "ok":
                _fail(f"health reported {health!r}")
        finally:
            _run([executable, "service", "stop"], env=environment)
        _check_database(root / "data" / "downcroc" / "downcroc.db")
        service = root / "state" / "downcroc" / "service.json"
        token = root / "state" / "downcroc" / "daemon.token"
        if service.exists() or token.exists():
            _fail("clean stop left service.json or daemon.token behind")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test an installed downcroc wheel"
    )
    parser.add_argument(
        "--bin", required=True, type=Path, help="installed script directory"
    )
    parser.add_argument(
        "--dist", required=True, type=Path, help="directory with built artifacts"
    )
    args = parser.parse_args(argv)

    executable = shutil.which("downcroc", path=str(args.bin))
    if executable is None:
        _fail(f"no downcroc executable in {args.bin}")
    _check_artifacts(args.dist)
    expected = _check_metadata()
    _check_version(executable, expected)
    _smoke_daemon(executable, expected)
    print(f"wheel smoke passed for downcroc {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

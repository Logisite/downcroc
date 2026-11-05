"""Benchmark downcroc startup paths in an isolated HOME.

This does not touch the real config, data, state, vault, or logs. It creates
a temporary home, writes a disposable config pointing at a free port, starts
and stops the real daemon, and prints wall-clock timings.

Examples:
    uv run python scripts/benchmark_startup.py
    uv run python scripts/benchmark_startup.py --skip-daemon
    uv run python scripts/benchmark_startup.py --daemon-runs 2 --keep
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

ROOT = Path(__file__).resolve().parents[1]
BENCH_TMP = Path("/tmp/opencode")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def isolated_env(home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "NO_COLOR": "1",
    }


def write_config(home: Path, port: int) -> None:
    config = home / ".config" / "downcroc" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f"[daemon]\nport = {port}\nstart_timeout_s = 60.0\n",
        encoding="utf-8",
    )


def read_log(home: Path) -> list[dict]:
    path = home / ".local" / "share" / "downcroc" / "logs" / "downcroc.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def clock(rows: list[dict], event: str) -> str | None:
    for row in reversed(rows):
        if row.get("event") == event:
            return str(row.get("ts", ""))
    return None


def elapsed_ms(rows: list[dict], start: str, end: str) -> float | None:
    first = next((row for row in reversed(rows) if row.get("event") == start), None)
    last = next((row for row in reversed(rows) if row.get("event") == end), None)
    if first is None or last is None:
        return None
    try:
        from datetime import datetime

        begin = datetime.fromisoformat(str(first["ts"]))
        finish = datetime.fromisoformat(str(last["ts"]))
        return (finish - begin).total_seconds() * 1000
    except ValueError, KeyError:
        return None


def run(args: list[str], env: dict[str, str], timeout: float = 180.0):
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return result, time.monotonic() - started


def print_row(label: str, seconds: float, suffix: str = "") -> None:
    print(f"{label:<34} {seconds * 1000:9.0f}ms {suffix}")


def bench_command(name: str, args: list[str], env: dict[str, str], runs: int) -> None:
    for _ in range(runs):
        result, elapsed = run(args, env)
        print(f"{name:<34} {elapsed * 1000:9.0f}ms rc={result.returncode}")
        if result.returncode:
            print(f"  stderr: {result.stderr.strip().splitlines()[:2]}")


def bench_import(name: str, module: str, runs: int) -> None:
    for _ in range(runs):
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-X", "importtime", "-c", f"import {module}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        elapsed = time.monotonic() - started
        print(f"import {module:<24} {elapsed * 1000:9.0f}ms rc={result.returncode}")


def bench_endpoints(port: int, home: Path) -> None:
    if httpx is None:
        print("endpoint timings skipped (httpx unavailable)")
        return
    token_path = home / ".local" / "state" / "downcroc" / "daemon.token"
    if not token_path.is_file():
        print("endpoint timings skipped (token missing)")
        return
    token = token_path.read_text(encoding="utf-8").strip()
    base_url = f"http://127.0.0.1:{port}"
    paths = (
        "/api/health",
        "/api/vault",
        "/api/accounts",
        "/api/stats/summary",
        "/api/status",
        "/api/failed?limit=1",
    )
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        trust_env=False,
        timeout=10.0,
    ) as client:
        for path in paths:
            started = time.monotonic()
            response = client.get(path)
            elapsed = time.monotonic() - started
            print(
                f"GET {path:<22} {elapsed * 1000:9.0f}ms status={response.status_code}"
            )


def bench_daemon(home: Path, env: dict[str, str], runs: int, endpoints: bool) -> None:
    port = free_port()
    write_config(home, port)
    try:
        for iteration in range(1, runs + 1):
            result, elapsed = run(["service", "start"], env, timeout=180.0)
            print(
                f"daemon start run {iteration:<4} {elapsed * 1000:9.0f}ms rc={result.returncode}"
            )
            if result.returncode:
                print("stdout:", result.stdout.strip())
                print("stderr:", result.stderr.strip())
                return
            rows = read_log(home)
            boot = elapsed_ms(rows, "daemon.start", "daemon.ready")
            start_ms = elapsed_ms(rows, "daemon.start", "db.migrate")
            migrate_ms = next(
                (
                    float(row.get("duration_ms", 0.0))
                    for row in reversed(rows)
                    if row.get("event") == "db.migrate"
                ),
                None,
            )
            print(
                f"  daemon.start -> ready {boot:9.0f}ms"
                f"   migrate {migrate_ms or -1:6.0f}ms"
                f"   spawn -> migrate {start_ms or -1:6.0f}ms"
            )
            if endpoints:
                bench_endpoints(port, home)
            stopped, stop_elapsed = run(["service", "stop"], env, timeout=30.0)
            print(
                f"daemon stop              {stop_elapsed * 1000:9.0f}ms rc={stopped.returncode}"
            )
    finally:
        run(["service", "stop"], env, timeout=30.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=2, help="command timing runs")
    parser.add_argument("--import-runs", type=int, default=1, help="import timing runs")
    parser.add_argument("--daemon-runs", type=int, default=1, help="daemon timing runs")
    parser.add_argument("--skip-daemon", action="store_true", help="skip daemon timing")
    parser.add_argument("--endpoints", action="store_true", help="time API endpoints")
    parser.add_argument("--keep", action="store_true", help="keep the temporary home")
    args = parser.parse_args(argv)

    home = Path(tempfile.mkdtemp(prefix="downcroc-benchmark-", dir=BENCH_TMP))
    env = isolated_env(home)
    print(f"home: {home}")
    print(f"python: {sys.version.split()[0]}")
    print()
    bench_command("downcroc --version", ["--version"], env, args.runs)
    print()
    for module in ("downcroc.cli.main", "downcroc.api.app", "downcroc.core.bootstrap"):
        bench_import(module, module, args.import_runs)
    print()
    if not args.skip_daemon:
        bench_daemon(home, env, args.daemon_runs, args.endpoints)
    else:
        print("daemon timing skipped")
    print()
    if args.keep:
        print(f"keep: {home}")
    else:
        shutil.rmtree(home, ignore_errors=True)
        print("home: removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

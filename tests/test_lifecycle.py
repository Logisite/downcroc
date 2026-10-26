from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.harness.daemon import free_port

ROOT = Path(__file__).resolve().parents[1]


def _environment(root: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
    }


def _run(
    env: dict[str, str],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "downcroc", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _json(
    env: dict[str, str],
    *args: str,
) -> dict | list:
    result = _run(env, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _write_config(root: Path, **fields: object) -> int:
    port = int(fields.pop("port", free_port()))
    lines = ["[daemon]", f"port = {port}", "start_timeout_s = 120.0"]
    lines.extend(f"{name} = {value!r}" for name, value in fields.items())
    path = root / "config" / "downcroc" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return port


def _wait(predicate, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not become true")


def _service_path(root: Path, name: str) -> Path:
    return root / "state" / "downcroc" / name


def _stop(env: dict[str, str]) -> None:
    _run(env, "service", "stop")


def _kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            check=False,
            timeout=30,
        )
        return
    os.kill(pid, 9)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_empty_home_starts_serves_and_stops(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    env = _environment(root)
    try:
        started = _run(env, "service", "start")
        assert started.returncode == 0, started.stderr
        service = _service_path(root, "service.json")
        token = _service_path(root, "daemon.token")
        config = root / "config" / "downcroc" / "config.toml"
        log = root / "data" / "downcroc" / "logs" / "downcroc.jsonl"
        assert service.is_file()
        assert token.is_file()
        assert config.is_file()
        assert log.is_file()
        status = _json(env, "service", "status", "--json")
        assert status["state"] == "running"
        if os.name != "nt":
            for path in (
                root / "config" / "downcroc",
                root / "data" / "downcroc",
                root / "state" / "downcroc",
                root / "data" / "downcroc" / "logs",
            ):
                assert _mode(path) == 0o700
            for path in (config, log, service, token):
                assert _mode(path) == 0o600
    finally:
        _stop(env)
    assert not _service_path(root, "service.json").exists()
    assert not _service_path(root, "daemon.token").exists()
    assert _json(env, "service", "status", "--json") == {"state": "stopped"}


def test_shutdown_requires_the_control_token(tmp_path: Path) -> None:
    root = tmp_path / "token"
    port = _write_config(root)
    env = _environment(root)
    try:
        started = _run(env, "service", "start")
        assert started.returncode == 0, started.stderr
        service = _service_path(root, "service.json")
        token_path = _service_path(root, "daemon.token")
        info = json.loads(service.read_text())
        base = f"http://127.0.0.1:{port}"
        with httpx.Client(trust_env=False, timeout=5.0) as client:
            refused = client.post(f"{base}/api/service/stop")
            assert refused.status_code == 401
            assert service.is_file()
            accepted = client.post(
                f"{base}/api/service/stop",
                headers={"Authorization": f"Bearer {token_path.read_text().strip()}"},
            )
            assert accepted.status_code == 200
        _wait(lambda: not service.exists(), timeout=30)
        assert not token_path.exists()
        assert info["pid"] > 0
        assert _run(env, "service", "start").returncode == 0
    finally:
        _stop(env)


def test_second_start_names_the_running_daemon(tmp_path: Path) -> None:
    root = tmp_path / "second"
    _write_config(root)
    env = _environment(root)
    try:
        first = _run(env, "service", "start")
        assert first.returncode == 0, first.stderr
        pid = json.loads(_service_path(root, "service.json").read_text())["pid"]
        second = _run(env, "service", "start")
        assert second.returncode == 1
        assert str(pid) in second.stderr
    finally:
        _stop(env)


def test_killed_daemon_does_not_block_the_next_start(tmp_path: Path) -> None:
    root = tmp_path / "killed"
    port = _write_config(root)
    env = _environment(root)
    try:
        first = _run(env, "service", "start")
        assert first.returncode == 0, first.stderr
        pid = json.loads(_service_path(root, "service.json").read_text())["pid"]
        _kill(pid)
        _wait(lambda: not _service_reachable(root), timeout=30)
        _wait(lambda: _port_free(port), timeout=30)
        restarted = _run(env, "service", "start")
        assert restarted.returncode == 0, restarted.stderr
        assert _json(env, "service", "status", "--json")["state"] == "running"
    finally:
        _stop(env)


def test_invalid_config_is_rejected_with_the_field_and_no_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "invalid"
    path = root / "config" / "downcroc" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[daemon]\nhost = "0.0.0.0"\n')
    env = _environment(root)
    result = _run(env, "service", "start")
    assert result.returncode == 1
    assert "daemon.host" in result.stderr
    assert "loopback" in result.stderr
    assert not _service_path(root, "service.json").exists()
    assert not _service_path(root, "daemon.token").exists()


def _service_reachable(root: Path) -> bool:
    service = _service_path(root, "service.json")
    if not service.is_file():
        return False
    try:
        info = json.loads(service.read_text())
    except OSError, ValueError:
        return False
    try:
        response = httpx.get(
            f"http://127.0.0.1:{info['port']}/api/health",
            timeout=0.5,
            trust_env=False,
        )
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _port_free(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


@pytest.mark.parametrize("action", ["status", "stop"])
def test_service_commands_work_without_a_config(
    tmp_path: Path,
    action: str,
) -> None:
    root = tmp_path / "bare"
    env = _environment(root)
    result = _run(env, "service", action)
    assert result.returncode == 0, result.stderr

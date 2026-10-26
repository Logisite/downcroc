from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from downcroc.runtime.service.process import is_alive, kill, terminate

from .fakes import FakeMailServers

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Daemon:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config_home = root / "config"
        self.data_home = root / "data"
        self.state_home = root / "state"
        self.home = root / "home"
        self.config = self.config_home / "downcroc"
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[bytes] | None = None
        self.stdout = root / "daemon.out"
        self.stderr = root / "daemon.err"

    def start(
        self,
        fakes: FakeMailServers,
        config_extra: str = "",
        preserve_config: bool = False,
    ) -> Daemon:
        for directory in (
            self.config,
            self.data_home,
            self.state_home,
            self.home,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        if not preserve_config:
            (self.config / "providers.toml").write_text(fakes.providers_toml)
            (self.config / "config.toml").write_text(
                "[daemon]\n"
                f"port = {self.port}\n"
                "start_timeout_s = 120.0\n"
                "\n"
                "[intake]\n"
                "sample_count = 5\n"
                f"{config_extra}"
            )
        env = self.environment()
        out = self.stdout.open("wb")
        err = self.stderr.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "downcroc", "serve"],
            cwd=ROOT,
            env=env,
            stdout=out,
            stderr=err,
        )
        try:
            self.wait_ready()
        except Exception:
            self.stop()
            raise
        return self

    def environment(self) -> dict[str, str]:
        return {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config_home),
            "XDG_DATA_HOME": str(self.data_home),
            "XDG_STATE_HOME": str(self.state_home),
        }

    def wait_ready(self, timeout: float = 180.0) -> None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    f"daemon exited with {self.process.returncode}: {self._tail()}"
                )
            try:
                with opener.open(f"{self.base_url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except urllib.error.URLError, TimeoutError, ConnectionError:
                time.sleep(0.05)
        raise RuntimeError(f"daemon did not become ready: {self._tail()}")

    def _service_pid(self) -> int | None:
        path = self.state_home / "downcroc" / "service.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return int(payload["pid"])
        except OSError, KeyError, TypeError, ValueError:
            return None

    def _pids(self) -> list[int]:
        pids: list[int] = []
        if self.process is not None and self.process.poll() is None:
            pids.append(self.process.pid)
        service = self._service_pid()
        if service is not None and service not in pids:
            pids.append(service)
        return pids

    def _alive(self, pid: int) -> bool:
        if self.process is not None and pid == self.process.pid:
            return self.process.poll() is None
        return is_alive(pid)

    def _wait_pids(self, pids: list[int], timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(self._alive(pid) for pid in pids):
                return
            time.sleep(0.05)

    def stop(self) -> None:
        pids = self._pids()
        for pid in pids:
            terminate(pid)
        self._wait_pids(pids, 15.0)
        for pid in pids:
            if self._alive(pid):
                kill(pid)
        if self.process is not None:
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def kill(self) -> None:
        pids = self._pids()
        for pid in pids:
            kill(pid)
        self._wait_pids(pids, 10.0)
        if self.process is not None:
            self.process.wait(timeout=10)

    def wait_stopped(self, timeout: float = 20.0) -> int:
        if self.process is None:
            return 0
        return self.process.wait(timeout=timeout)

    def _tail(self) -> str:
        parts = []
        for path in (self.stderr, self.stdout):
            if path.exists():
                parts.append(path.read_text(errors="replace")[-4000:])
        return "\n".join(parts)

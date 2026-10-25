from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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

    def start(self, fakes: FakeMailServers, config_extra: str = "") -> Daemon:
        for directory in (
            self.config,
            self.data_home,
            self.state_home,
            self.home,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (self.config / "providers.toml").write_text(fakes.providers_toml)
        (self.config / "config.toml").write_text(
            "[daemon]\n"
            f"port = {self.port}\n"
            "start_timeout_s = 10.0\n"
            "\n"
            "[intake]\n"
            "sample_count = 5\n"
            f"{config_extra}"
        )
        env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config_home),
            "XDG_DATA_HOME": str(self.data_home),
            "XDG_STATE_HOME": str(self.state_home),
        }
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

    def wait_ready(self, timeout: float = 90.0) -> None:
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

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def _tail(self) -> str:
        parts = []
        for path in (self.stderr, self.stdout):
            if path.exists():
                parts.append(path.read_text(errors="replace")[-4000:])
        return "\n".join(parts)

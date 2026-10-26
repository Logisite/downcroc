from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from types import FrameType

import httpx
import uvicorn
from fastapi import FastAPI

from downcroc.api.app import create_app
from downcroc.backup.restore import log_outcome, perform_pending
from downcroc.domain.errors import RestoreFailed
from downcroc.runtime.config.loader import ConfigError, load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.paths import Paths, ensure
from downcroc.runtime.service.lock import AlreadyRunning, InstanceLock, running
from downcroc.runtime.service.registry import ServiceInfo, read, remove, write
from downcroc.version import API_VERSION, __version__


class PortInUse(RuntimeError):
    pass


class DaemonServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, app: FastAPI) -> None:
        super().__init__(config)
        self._app = app
        self.received: list[int] = []

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        self.received.append(sig)
        services = getattr(self._app.state, "services", None)
        if services is not None:
            services.inbound.stop_all("shutdown")
            services.accounts.close_flows("daemon_stopped")
            services.vault.lock("shutdown")
            services.bus.close_all("shutdown")
        super().handle_exit(sig, frame)

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        previous = {
            sig: signal.signal(sig, self.handle_exit)
            for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def _check_port(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as error:
            raise PortInUse(f"port {port} is not free: {error.strerror}") from error


def _health(info: ServiceInfo, timeout: float = 1.0) -> dict | None:
    try:
        response = httpx.get(f"{info.base_url}/api/health", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def run_foreground(paths: Paths) -> None:
    lock = InstanceLock(paths.lock_file)
    try:
        lock.acquire()
    except AlreadyRunning:
        existing = running(paths.service_file)
        if paths.data.is_dir():
            try:
                log = setup_logging(paths, Settings(), stream=sys.stderr)
                log.warning(
                    "lock.refused",
                    pid=existing.pid if existing else None,
                    port=existing.port if existing else None,
                )
            except OSError:
                pass
        detail = f" on pid {existing.pid}" if existing else ""
        raise SystemExit(f"downcroc is already running{detail}") from None

    try:
        try:
            outcome = perform_pending(paths)
        except (RestoreFailed, OSError) as error:
            print(f"restore failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        ensure(paths)
        early = setup_logging(paths, Settings(), stream=sys.stderr)
        early.info("lock.acquired", path=str(paths.lock_file))
        if outcome is not None:
            log_outcome(early, outcome)

        try:
            settings, created = load_or_create(paths.config_file)
        except ConfigError as error:
            detail = f"{error.field}: {error}" if error.field else str(error)
            early.error("config.invalid", field=error.field, reason=str(error))
            print(f"config error: {detail}", file=sys.stderr)
            raise SystemExit(1) from error

        log = setup_logging(paths, settings, stream=sys.stderr)
        log.info(
            "config.loaded",
            path=str(paths.config_file),
            first_run=created,
            keys=",".join(settings.model_dump().keys()),
        )
        info = ServiceInfo(
            pid=os.getpid(),
            host=settings.daemon.host,
            port=settings.daemon.port,
            started_at=_now(),
            version=__version__,
            api_version=API_VERSION,
        )
        try:
            _check_port(info.host, info.port)
        except PortInUse as error:
            log.error("daemon.start_failed", reason=str(error))
            raise SystemExit(str(error)) from error
        write(paths.service_file, info)
        log.info(
            "daemon.start",
            pid=info.pid,
            host=info.host,
            port=info.port,
            version=info.version,
            config=str(paths.config_file),
        )
        app = create_app(settings, paths, log)
        server = DaemonServer(
            uvicorn.Config(
                app,
                host=info.host,
                port=info.port,
                log_config=None,
                access_log=False,
            ),
            app,
        )
        boot = time.monotonic()
        try:
            server.run()
        finally:
            stop_signal = (
                signal.Signals(server.received[0]).name if server.received else "none"
            )
            log.info(
                "daemon.stopping",
                signal=stop_signal,
                uptime_s=round(time.monotonic() - boot, 3),
            )
            remove(paths.service_file)
    finally:
        lock.release()


def start(paths: Paths, settings: Settings) -> ServiceInfo:
    existing = running(paths.service_file)
    if existing is not None:
        raise AlreadyRunning(existing)
    remove(paths.service_file)
    _check_port(settings.daemon.host, settings.daemon.port)
    process = subprocess.Popen(
        [sys.executable, "-m", "downcroc", "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + settings.daemon.start_timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"daemon exited during start, see {paths.log_file}")
        info = read(paths.service_file)
        if info is not None and info.pid == process.pid and _health(info):
            return info
        time.sleep(0.1)
    raise TimeoutError(
        f"daemon did not answer within {settings.daemon.start_timeout_s}s"
    )


def stop(paths: Paths, settings: Settings) -> bool:
    info = read(paths.service_file)
    if info is None or not _alive(info.pid):
        remove(paths.service_file)
        return False
    try:
        os.kill(info.pid, signal.SIGTERM)
    except ProcessLookupError:
        remove(paths.service_file)
        return False
    deadline = time.monotonic() + settings.daemon.stop_timeout_s
    while time.monotonic() < deadline:
        if not _alive(info.pid):
            remove(paths.service_file)
            return True
        time.sleep(0.1)
    os.kill(info.pid, signal.SIGKILL)
    remove(paths.service_file)
    return True


def status(paths: Paths) -> dict:
    info = read(paths.service_file)
    if info is None:
        return {"state": "stopped"}
    if not _alive(info.pid):
        return {"state": "stale", "pid": info.pid, "port": info.port}
    health = _health(info)
    report = {
        "state": "running",
        "pid": info.pid,
        "host": info.host,
        "port": info.port,
        "version": info.version,
        "started_at": info.started_at,
        "url": info.base_url,
    }
    if health is None:
        report["state"] = "unreachable"
    else:
        report["uptime_s"] = health.get("uptime_s")
    return report

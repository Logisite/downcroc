from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

import httpx
import uvicorn

from downcroc.api.app import create_app
from downcroc.backup.restore import log_outcome, perform_pending
from downcroc.domain.errors import RestoreFailed
from downcroc.runtime.config.loader import ConfigError, load_or_create
from downcroc.runtime.config.schema import Settings
from downcroc.runtime.logging.setup import setup_logging
from downcroc.runtime.paths import Paths, ensure
from downcroc.runtime.service import token as service_token
from downcroc.runtime.service.lock import AlreadyRunning, InstanceLock, running
from downcroc.runtime.service.process import (
    detached_kwargs,
    is_alive,
    kill,
    terminate,
)
from downcroc.runtime.service.registry import ServiceInfo, read, remove, write
from downcroc.runtime.service.units import launcher
from downcroc.version import API_VERSION, __version__


class PortInUse(RuntimeError):
    pass


class DaemonServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.received: list[int] = []

    def request_shutdown(self) -> None:
        self.should_exit = True

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        self.received.append(sig)
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


def _log_tail(path: Path, limit: int = 2000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
    except OSError:
        return ""


def _health(info: ServiceInfo, timeout: float = 1.0) -> dict | None:
    try:
        response = httpx.get(
            f"{info.base_url}/api/health",
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def _request_stop(info: ServiceInfo, token: str | None) -> bool:
    if not token:
        return False
    try:
        response = httpx.post(
            f"{info.base_url}/api/service/stop",
            headers={"Authorization": f"Bearer {token}"},
            timeout=2.0,
            trust_env=False,
        )
    except httpx.HTTPError:
        return False
    return response.status_code < 400


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _wait_dead(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_alive(pid):
            return True
        time.sleep(0.1)
    return not is_alive(pid)


def _terminate_pid(pid: int, timeout: float = 5.0) -> None:
    if not is_alive(pid):
        return
    terminate(pid)
    if _wait_dead(pid, timeout):
        return
    kill(pid)
    _wait_dead(pid, timeout)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _cleanup(paths: Paths) -> None:
    remove(paths.service_file)
    service_token.clear(paths.token_file)


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
            keys=list(settings.model_dump().keys()),
        )
        token = service_token.issue(paths.token_file)
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
            _cleanup(paths)
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
        app = create_app(settings, paths, log, token=token)
        server = DaemonServer(
            uvicorn.Config(
                app,
                host=info.host,
                port=info.port,
                log_config=None,
                access_log=False,
            )
        )
        app.state.request_shutdown = server.request_shutdown
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
            _cleanup(paths)
    finally:
        lock.release()


def start(
    paths: Paths,
    settings: Settings,
    *,
    timeout: float | None = None,
    progress: Callable[[str, float | None], None] | None = None,
) -> ServiceInfo:
    existing = running(paths.service_file)
    if existing is not None:
        raise AlreadyRunning(existing)
    _cleanup(paths)
    _check_port(settings.daemon.host, settings.daemon.port)
    if progress is not None:
        progress(
            f"starting on {settings.daemon.host}:{settings.daemon.port} ...",
            0.0,
        )
    process = subprocess.Popen(
        [*launcher(), "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **detached_kwargs(),
    )
    service_pid: int | None = None
    limit = settings.daemon.start_timeout_s if timeout is None else timeout
    started = time.monotonic()
    try:
        deadline = started + limit
        while time.monotonic() < deadline:
            info = read(paths.service_file)
            if info is not None:
                service_pid = info.pid
                if _health(info):
                    if progress is not None:
                        progress(
                            f"ready after {time.monotonic() - started:.1f}s "
                            f"on {info.base_url}",
                            1.0,
                        )
                    return info
            if process.poll() is not None and (info is None or not is_alive(info.pid)):
                raise RuntimeError(f"daemon exited during start, see {paths.log_file}")
            if progress is not None:
                progress(
                    f"waiting for health ... {time.monotonic() - started:.1f}s"
                    f" of {limit:.0f}s",
                    None,
                )
            time.sleep(0.1)
        tail = _log_tail(paths.log_file)
        detail = f"\n{tail}" if tail else ""
        raise TimeoutError(
            f"daemon did not answer within {limit:.0f}s "
            f"(launcher pid {process.pid}, service pid {service_pid}); "
            f"see {paths.log_file}{detail}"
        )
    except BaseException:
        if service_pid is not None:
            _terminate_pid(service_pid)
        _terminate(process)
        _cleanup(paths)
        raise


def stop(paths: Paths, settings: Settings) -> bool:
    info = read(paths.service_file)
    if info is None or not is_alive(info.pid):
        _cleanup(paths)
        return False
    token = service_token.read(paths.token_file)
    if _request_stop(info, token):
        deadline = time.monotonic() + settings.daemon.stop_timeout_s
    else:
        terminate(info.pid)
        deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not is_alive(info.pid):
            _cleanup(paths)
            return True
        time.sleep(0.1)
    kill(info.pid)
    _wait_dead(info.pid, 5.0)
    _cleanup(paths)
    return True


def status(paths: Paths) -> dict:
    info = read(paths.service_file)
    if info is None:
        return {"state": "stopped"}
    if not is_alive(info.pid):
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

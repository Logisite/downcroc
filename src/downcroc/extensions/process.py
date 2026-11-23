from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from typing import Any

from downcroc.extensions.errors import ExtensionCrashed, ExtensionTimeout
from downcroc.extensions.manifest import Manifest


class ExtensionProcess:
    def __init__(
        self,
        manifest: Manifest,
        grants: frozenset[str],
        settings: dict[str, Any],
        timeout: float,
    ) -> None:
        self.manifest = manifest
        self.grants = grants
        self.settings = settings
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.inbox: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("DOWNCROC_", "XDG_", "HOME", "USERPROFILE"))
        }
        env["PATH"] = os.environ.get("PATH", "")
        self.process = subprocess.Popen(
            list(self.manifest.run),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._send(
            {
                "type": "hello",
                "extension": self.manifest.id,
                "capabilities": sorted(self.grants),
                "settings": self.settings,
            }
        )

    def _read(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            self.inbox.put(line)

    def exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self._send({"type": "event", "payload": payload})
            try:
                line = self.inbox.get(timeout=self.timeout)
            except queue.Empty as error:
                raise ExtensionTimeout("extension did not respond") from error
            try:
                message = json.loads(line)
            except ValueError as error:
                raise ExtensionCrashed("extension returned invalid json") from error
            if self.process is not None and self.process.poll() is not None:
                raise ExtensionCrashed("extension exited")
            return message

    def respond(self, results: list[Any]) -> None:
        self._send({"type": "result", "results": results})

    def _send(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise ExtensionCrashed("extension is not running")
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)

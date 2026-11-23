from __future__ import annotations

import asyncio
import importlib
import threading
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from downcroc.extensions import packaging
from downcroc.extensions.broker import Broker
from downcroc.extensions.config import ExtensionConfig, ExtensionSettings
from downcroc.extensions.errors import (
    ExtensionCrashed,
    ExtensionError,
    ExtensionNotFound,
    ExtensionTimeout,
)
from downcroc.extensions.events import sanitize
from downcroc.extensions.manifest import Manifest, load_manifests
from downcroc.extensions.process import ExtensionProcess
from downcroc.extensions.store import ExtensionStore
from downcroc.runtime.logging.setup import EventLogger
from downcroc.runtime.paths import Paths


@dataclass
class Registered:
    manifest: Manifest
    config: ExtensionConfig
    process: ExtensionProcess | InProcessExtension | None = None
    restarts: int = 0


class InProcessExtension:
    def __init__(
        self, manifest: Manifest, broker: Broker, grants: frozenset[str]
    ) -> None:
        module_name = next(
            (item for item in manifest.run if item.startswith(("-m", "--module"))),
            None,
        )
        if module_name is None:
            raise ExtensionCrashed("in-process mode needs -m module")
        index = manifest.run.index(module_name)
        if index + 1 >= len(manifest.run):
            raise ExtensionCrashed("in-process mode needs a module name")
        module = importlib.import_module(manifest.run[index + 1])
        self.module = module
        self.broker = broker
        self.extension = manifest.id
        self.grants = grants

    def exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        handle = getattr(self.module, "handle", None)
        if handle is None:
            return {"actions": []}
        response = handle(payload, Context(self))
        return response if isinstance(response, dict) else {"actions": []}

    def respond(self, results: list[Any]) -> None:
        del results

    def alive(self) -> bool:
        return True

    def stop(self) -> None:
        return None


class Context:
    def __init__(self, extension: InProcessExtension) -> None:
        self.extension = extension

    def call(self, capability: str, **params: Any) -> Any:
        return self.extension.broker.call(
            self.extension.extension,
            capability,
            params,
            self.extension.grants,
            {},
        )


class ExtensionHost:
    def __init__(
        self,
        paths: Paths,
        settings: ExtensionSettings,
        manifests: list[Manifest],
        broker: Broker,
        store: ExtensionStore,
        log: EventLogger,
        bus: Any,
    ) -> None:
        self.bus = bus
        self.paths = paths
        self.settings = settings
        self.broker = broker
        self.store = store
        self.log = log
        self.registered: dict[str, Registered] = {}
        self._user_config: dict[str, Any] = {}
        for manifest in manifests:
            self.registered[manifest.id] = Registered(
                manifest, self._config_for(manifest)
            )
        self._lock = threading.Lock()

    def _config_for(self, manifest: Manifest) -> ExtensionConfig:
        section = self._user_config.get(manifest.config_key)
        if not isinstance(section, dict):
            section = {}
        try:
            return ExtensionConfig(**section)
        except ValidationError:
            return ExtensionConfig()

    def load_config(self) -> None:
        try:
            with self.paths.config_file.open("rb") as handle:
                data = tomllib.load(handle)
        except OSError, ValueError:
            data = {}
        section = data.get("extensions")
        self._user_config = section if isinstance(section, dict) else {}
        for item in self.registered.values():
            item.config = self._config_for(item.manifest)

    def start(self) -> None:
        if not self.settings.enabled:
            return
        self.load_config()
        for item in self.registered.values():
            if item.config.enabled and item.process is None:
                self._launch(item)

    async def pump(self) -> None:
        subscription = self.bus.subscribe()
        try:
            while True:
                event = await subscription.queue.get()
                if event is None:
                    return
                await asyncio.to_thread(self.publish, event.type, event.data)
        finally:
            self.bus.unsubscribe(subscription)

    def _artifact_manifest(self, item: Registered) -> Manifest | None:
        if item.manifest.kind != "pyz":
            return item.manifest
        if not packaging.verify(item.manifest, self._config_dir()):
            self.log.error(
                "extension.artifact_invalid",
                extension=item.manifest.id,
                detail="artifact missing or checksum mismatch",
            )
            return None
        command = packaging.command(item.manifest, self._config_dir())
        return replace(item.manifest, run=command)

    def _launch(self, item: Registered) -> None:
        manifest = self._artifact_manifest(item)
        if manifest is None:
            item.restarts += 1
            return
        grants = frozenset(item.config.allow or item.manifest.capabilities)
        try:
            if item.config.trust:
                process: ExtensionProcess | InProcessExtension = InProcessExtension(
                    manifest, self.broker, grants
                )
            else:
                process = ExtensionProcess(
                    manifest,
                    grants,
                    item.config.settings,
                    self.settings.call_timeout_s,
                )
                process.start()
        except (OSError, ExtensionError, ImportError, ValueError, TypeError) as error:
            self.log.error(
                "extension.crashed",
                extension=item.manifest.id,
                error=type(error).__name__,
                detail=str(error)[:200],
            )
            item.restarts += 1
            return
        item.process = process
        state = self.store.state(item.manifest.id) or {}
        self.store.save_state(
            item.manifest.id,
            version=item.manifest.version,
            enabled=True,
            restarts=int(state.get("restarts", 0)),
        )
        self.log.info(
            "extension.started",
            extension=item.manifest.id,
            mode="inprocess" if item.config.trust else "subprocess",
        )

    def publish(self, event: str, payload: dict[str, Any]) -> None:
        if not self.settings.enabled:
            return
        for item in self.registered.values():
            if not item.config.enabled or item.process is None:
                continue
            if not self._subscribed(item.manifest, event):
                continue
            event_payload = sanitize(payload)
            if event_payload.get("extension") == item.manifest.id:
                continue
            if int(event_payload.get("extension_depth", 0)) >= 3:
                continue
            self._dispatch(item, event, event_payload)

    def invoke(self, extension: str, command: str, args: dict[str, Any]) -> Any:
        item = self._get(extension)
        payload = sanitize(
            {"event": f"command:{command}", "extension_depth": 0, "args": args}
        )
        return self._dispatch(item, payload["event"], payload)

    def run_once(self, extension: str, payload: dict[str, Any]) -> Any:
        item = self._get(extension)
        manifest = self._artifact_manifest(item)
        if manifest is None:
            raise ExtensionError("extension artifact is missing or changed")
        grants = frozenset(item.config.allow or item.manifest.capabilities)
        process = ExtensionProcess(
            manifest, grants, item.config.settings, self.settings.call_timeout_s
        )
        process.start()
        try:
            response = process.exchange(sanitize(payload))
            return self._execute(item, response)[0]
        finally:
            process.stop()

    def enable(self, extension: str) -> None:
        item = self._get(extension)
        item.config.enabled = True
        state = self.store.state(extension) or {}
        self.store.save_state(
            extension,
            version=item.manifest.version,
            enabled=True,
            restarts=int(state.get("restarts", 0)),
        )
        if item.process is None:
            self._launch(item)

    def disable(self, extension: str) -> None:
        item = self._get(extension)
        item.config.enabled = False
        state = self.store.state(extension) or {}
        self.store.save_state(
            extension,
            version=item.manifest.version,
            enabled=False,
            restarts=int(state.get("restarts", 0)),
        )
        if item.process is not None:
            item.process.stop()
            item.process = None
        self.log.info("extension.stopped", extension=extension, reason="disabled")

    def reload(self) -> None:
        for item in self.registered.values():
            if item.process is not None:
                item.process.stop()
                item.process = None
        self.load_config()
        directory = self.paths.config / self.settings.dir
        self.registered = {
            manifest.id: Registered(manifest, self._config_for(manifest))
            for manifest in load_manifests(directory)
        }
        self.start()

    def status(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item.manifest.id,
                "name": item.manifest.name,
                "version": item.manifest.version,
                "enabled": item.config.enabled,
                "running": item.process is not None and item.process.alive(),
                "events": list(item.manifest.events),
                "commands": [command.name for command in item.manifest.commands],
                "kind": item.manifest.kind,
                "artifact": item.manifest.artifact,
                "artifact_verified": (
                    packaging.verify(item.manifest, self._config_dir())
                    if item.manifest.kind == "pyz"
                    else None
                ),
            }
            for item in self.registered.values()
        ]

    def verify(self, extension: str) -> dict[str, Any]:
        item = self._get(extension)
        if item.manifest.kind != "pyz":
            return {
                "extension": extension,
                "kind": item.manifest.kind,
                "verified": None,
            }
        verified = packaging.verify(item.manifest, self._config_dir())
        return {"extension": extension, "kind": "pyz", "verified": verified}

    def stop(self) -> None:
        for item in self.registered.values():
            if item.process is not None:
                item.process.stop()
                item.process = None

    def _config_dir(self) -> Path:
        return self.paths.config / self.settings.dir

    def _get(self, extension: str) -> Registered:
        item = self.registered.get(extension)
        if item is None:
            raise ExtensionNotFound(extension)
        return item

    def _dispatch(self, item: Registered, event: str, payload: dict[str, Any]) -> Any:
        if item.process is None:
            return None
        try:
            response = item.process.exchange({"event": event, **payload})
            result = self._execute(item, response)
            item.process.respond(result[1])
            return result[0]
        except (ExtensionTimeout, ExtensionCrashed) as error:
            self._crash(item, error)
            return None

    def _execute(
        self, item: Registered, response: dict[str, Any]
    ) -> tuple[Any, list[Any]]:
        actions = response.get("actions") or []
        results: list[Any] = []
        for action in actions:
            if not isinstance(action, dict):
                results.append({"error": "invalid action"})
                continue
            capability = str(action.get("capability", ""))
            params = dict(action.get("params") or action)
            params.pop("capability", None)
            try:
                results.append(
                    self.broker.call(
                        item.manifest.id,
                        capability,
                        params,
                        frozenset(item.config.allow or item.manifest.capabilities),
                        item.config.settings,
                    )
                )
            except (
                ExtensionError,
                ValueError,
                TypeError,
                KeyError,
                OSError,
                RuntimeError,
            ) as error:
                results.append(
                    {"error": type(error).__name__, "detail": str(error)[:200]}
                )
        return results, results

    def _crash(self, item: Registered, error: Exception) -> None:
        item.restarts += 1
        fields = {
            "extension": item.manifest.id,
            "error": type(error).__name__,
            "detail": str(error)[:200],
        }
        if isinstance(error, ExtensionCrashed):
            self.log.error("extension.crashed", **fields)
        else:
            self.log.error("extension.timeout", **fields)
        item.process = None
        if item.restarts <= self.settings.max_restarts:
            self._launch(item)

    @staticmethod
    def _subscribed(manifest: Manifest, event: str) -> bool:
        for wanted in manifest.events or ("*",):
            if wanted == "*" or event == wanted or event.startswith(f"{wanted}."):
                return True
        return False

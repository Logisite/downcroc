from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from downcroc.cli.commands.update import API, _version
from downcroc.runtime.paths import Paths
from downcroc.version import __version__

CACHE_NAME = "update-check.json"
TIMEOUT_S = 4.0


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    url: str | None


def _cache_path(paths: Paths) -> Path:
    return paths.state / CACHE_NAME


def _read(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return data if isinstance(data, dict) else None


def _write(path: Path, payload: dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _parse_feed(feed: object) -> UpdateInfo | None:
    if not isinstance(feed, list):
        return None
    releases = [
        item
        for item in feed
        if isinstance(item, dict)
        and not item.get("draft")
        and not item.get("prerelease")
        and isinstance(item.get("tag_name"), str)
    ]
    if not releases:
        return None
    latest = max(releases, key=lambda item: _version(str(item["tag_name"])))
    return UpdateInfo(
        current=__version__,
        latest=str(latest["tag_name"]).lstrip("vV"),
        url=str(latest["html_url"]) if latest.get("html_url") else None,
    )


def _fetch() -> UpdateInfo | None:
    try:
        response = httpx.get(
            API,
            timeout=TIMEOUT_S,
            trust_env=True,
            params={"per_page": 30},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "downcroc"},
        )
        if response.status_code != 200:
            return None
        return _parse_feed(response.json())
    except Exception:  # noqa: BLE001 - best effort, never fail a command
        return None


def _newer(info: UpdateInfo) -> bool:
    try:
        return _version(info.latest) > _version(info.current)
    except Exception:  # noqa: BLE001 - unparseable version means no prompt
        return False


def check(paths: Paths, interval_s: int) -> UpdateInfo | None:
    """Return update info when a newer release exists, else None.

    Reads a cached result first. When the cache is missing or older than
    ``interval_s``, fetches the release feed (best effort) and refreshes the
    cache. Never raises and never prints; callers decide how to present it.
    """
    cache = _read(_cache_path(paths))
    if cache is not None:
        checked_at = cache.get("checked_at")
        if (
            isinstance(checked_at, (int, float))
            and time.time() - checked_at < interval_s
        ):
            latest = cache.get("latest")
            current = cache.get("current", __version__)
            url = cache.get("url")
            if isinstance(latest, str):
                info = UpdateInfo(
                    current=str(current),
                    latest=latest,
                    url=str(url) if isinstance(url, str) else None,
                )
                return info if _newer(info) else None

    info = _fetch()
    if info is None:
        return None
    _write(
        _cache_path(paths),
        {
            "checked_at": time.time(),
            "current": info.current,
            "latest": info.latest,
            "url": info.url or "",
        },
    )
    return info if _newer(info) else None

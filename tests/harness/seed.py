from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .api import Api


def write_json(root: Path, name: str, document: Any) -> Path:
    path = root / name
    path.write_text(json.dumps(document, indent=2))
    return path


def write_csv(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.write_text(text)
    return path


def write_template(
    config_dir: Path,
    name: str,
    *,
    subject: str,
    body: str,
    html: str | None = None,
    attachments: list[str] | None = None,
    defaults: dict[str, str] | None = None,
) -> Path:
    directory = config_dir / "templates" / name
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f'subject = "{subject}"']
    if attachments:
        quoted = ", ".join(f'"{item}"' for item in attachments)
        lines.append(f"attachments = [{quoted}]")
    if defaults:
        lines.append("[defaults]")
        lines.extend(f'{key} = "{value}"' for key, value in defaults.items())
    (directory / "template.toml").write_text("\n".join(lines) + "\n")
    (directory / "body.txt").write_text(body)
    if html is not None:
        (directory / "body.html").write_text(html)
    return directory


def message(
    email: str,
    *,
    key: str | None = None,
    name: str | None = None,
    subject: str = "Hello",
    text: str = "Body",
    html: str | None = None,
    followups: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "to": {"email": email, "name": name},
        "subject": subject,
        "text": text,
    }
    if key is not None:
        document["key"] = key
    if html is not None:
        document["html"] = html
    if followups is not None:
        document["followups"] = followups
    document.update(extra)
    return document


def campaign(
    messages: list[dict[str, Any]],
    *,
    key: str = "test-campaign",
    name: str = "Test campaign",
    options: dict[str, Any] | None = None,
    routing: dict[str, Any] | None = None,
    followups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema": "downcroc.campaign/v1",
        "campaign": {"key": key, "name": name},
        "messages": messages,
    }
    if options is not None:
        document["campaign"]["options"] = options
    if routing is not None:
        document["campaign"]["routing"] = routing
    if followups is not None:
        document["followups"] = followups
    return document


def connect_accounts(api: Api, addresses: list[str]) -> list[str]:
    ids = []
    for address in addresses:
        account = api.create_account(address)
        api.connect(account["id"])
        ids.append(account["id"])
    return ids


def until(predicate: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition was not met before the timeout")

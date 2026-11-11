from __future__ import annotations

from datetime import UTC, datetime

from downcroc.cli.ui import panel
from downcroc.cli.ui.session import Ui


def show(ui: Ui, accounts: list[dict]) -> None:
    active = [item for item in accounts if item.get("status") != "pending"]
    checked = [item for item in active if item.get("auth_checked_at")]
    if not checked:
        return
    reconnect = [
        item
        for item in active
        if item.get("auth_action") == "reconnect"
        or item.get("auth_status") == "needs_reauth"
    ]
    unavailable = [item for item in active if item.get("auth_status") == "unavailable"]
    ready = [item for item in active if item.get("auth_status") == "ok"]
    tone = "bad" if unavailable else ("warn" if reconnect else "good")
    text = "   ".join(
        (
            ui.paint(f"{ui.glyph('ok')} {len(ready)} ready", "good"),
            ui.paint(
                f"{ui.glyph('warning')} {len(reconnect)} reconnect",
                "warn" if reconnect else "muted",
            ),
            ui.paint(
                f"{ui.glyph('dot')} {len(unavailable)} unavailable",
                "bad" if unavailable else "muted",
            ),
            ui.dim(f"{ui.glyph('clock')} {_age(checked)}"),
        )
    )
    for line in panel.status_line(ui, "credential check", text, tone):
        print(line)


def _age(checked: list[dict]) -> str:
    stamps: list[datetime] = []
    for item in checked:
        try:
            stamp = datetime.fromisoformat(str(item["auth_checked_at"]))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        stamps.append(stamp)
    if not stamps:
        return "just now"
    seconds = max(0, int((datetime.now(UTC) - max(stamps)).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"

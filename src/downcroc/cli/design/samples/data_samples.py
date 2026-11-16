"""Sample data for data/display primitives."""

from __future__ import annotations

TABLE_HEADERS = ["Field", "Value", "Count"]
TABLE_ROWS = [["account", "alice@example.com", "12"], ["status", "queued", "3"]]
TABLE_ALIGN = ["left", "left", "right"]

KV_ITEMS = [
    ("account", "alice@example.com"),
    ("mailbox", "inbox"),
    ("state", "connected"),
]
KV_COMPACT = [("mode", "compact"), ("sync", "idle")]

LIST_ITEMS = [
    "Queued and waiting",
    "Accepted by server and visible in sent folder history for later review",
    "Visible in sent folder",
]
ORDERED_ITEMS = ["Create job", "Review batch", "Send"]
TASK_ITEMS = [
    ("Connect mailbox", 0, True),
    ("Send first email", 0, False),
    ("Check logs", 0, False),
]

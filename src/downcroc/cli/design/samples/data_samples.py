"""Sample data for data/display primitives."""

from __future__ import annotations

TABLE_HEADERS = ["Field", "Value", "Count"]
TABLE_ROWS = [["account", "alice@example.com", "12"], ["status", "queued", "3"]]
TABLE_ALIGN = ["left", "left", "right"]

TABLE_SECTION_ROWS = [
    (["watcher", "running", "1"], True),
    ["sender", "queued", "4"],
    (["ingester", "idle", "0"], False),
]

KV_ITEMS = [
    ("account", "alice@example.com"),
    ("mailbox", "inbox"),
    ("state", "connected"),
]
KV_COMPACT = [("mode", "compact"), ("sync", "idle")]
KV_STACKED = [
    ("endpoint", "https://mail.example.test/inbound"),
    ("token", "••••••••••••"),
]

KV_WIDE = [
    ("service", "downcroc watcher"),
    ("last_sync", "2026-11-16 08:30:00"),
    ("notes", "healthy"),
]

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
NESTED_LIST_ITEMS = [
    ("Inbox", 0, None),
    ("Unread", 1, None),
    ("Starred", 1, None),
    ("Sent", 0, None),
]

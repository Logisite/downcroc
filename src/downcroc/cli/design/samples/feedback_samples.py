"""Sample data for feedback/navigation primitives."""

from __future__ import annotations

CALLOUTS = [
    ("Note", "note", "info", "Useful context for the reader."),
    ("Info", "info", "", "Explicit info tone uses the info icon by default."),
    ("Tip", "tip", "success", "A helpful suggestion."),
    ("Success", "success", "", "Operation completed successfully."),
    ("Warning", "warning", "", "Something needs attention."),
    ("Danger", "danger", "", "This action can cause data loss."),
    ("Example", "example", "", "An illustrative example callout."),
    ("Quote", "quote", "", "Quoted or cited guidance."),
]

TOASTS = [
    ("Connected to mailbox", "success"),
    ("Retry scheduled", "warning"),
    ("Delivery failed", "danger"),
    ("Sync info", "info"),
]

NAV_ITEMS = [
    ("Inbox", "inbox", True, 0, "12"),
    ("Sent", "sent", False, 0, ""),
    ("Archive", "folder", False, 1, ""),
]

TOC_ITEMS = [
    ("Overview", 1, True),
    ("Setup", 1, False),
    ("Troubleshooting", 2, False),
]

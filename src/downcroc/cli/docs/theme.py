from __future__ import annotations

from textual.theme import Theme

DOCS_THEME = Theme(
    name="downcroc",
    primary="#67e8f9",
    secondary="#818cf8",
    accent="#67e8f9",
    warning="#fbbf24",
    error="#fb7185",
    success="#4ade80",
    foreground="#e5e7eb",
    background="#0b1020",
    surface="#111827",
    panel="#1f2937",
    boost="#1f2937",
    dark=True,
    text_alpha=0.94,
    variables={
        "border": "#334155",
        "muted": "#94a3b8",
        "code": "#0f172a",
    },
)

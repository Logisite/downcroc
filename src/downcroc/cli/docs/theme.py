from __future__ import annotations

from textual.theme import Theme

# Aligned with design Theme "midnight" tokens for a cohesive custom docs shell.
DOCS_THEME = Theme(
    name="downcroc",
    primary="#7c6cf0",
    secondary="#58a6ff",
    accent="#7c6cf0",
    warning="#d29922",
    error="#f85149",
    success="#3fb950",
    foreground="#c9d1d9",
    background="#000000",
    surface="#16161e",
    panel="#1f1f2a",
    boost="#0f0f14",
    dark=True,
    text_alpha=0.96,
    variables={
        "border": "#232330",
        "border-strong": "#343444",
        "muted": "#626c7a",
        "text-muted": "#8b949e",
        "text-faint": "#3d4451",
        "code": "#0a0a10",
        "selected": "#16132b",
        "hover": "#0f0f14",
        "accent-dim": "#4c45a1",
        "accent-strong": "#9b8df7",
    },
)

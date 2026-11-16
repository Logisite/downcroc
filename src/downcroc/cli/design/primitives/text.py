"""Text bricks: styled runs and blocks, painted from theme tokens."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.style import Style
from rich.text import Text

from downcroc.cli.design.theme import Theme


def heading(text: str, theme: Theme, *, level: int = 1) -> Text:
    """Section heading. h1: bold primary; h2: accent bar; h3: muted marker."""
    level = max(1, min(level, 3))
    if level == 1:
        return Text(text, style=theme.style("fg_primary", bold=True))
    if level == 2:
        bar = Text("▏", style=theme.style("accent"))
        bar.append(" ", style=theme.style("bg_page"))
        bar.append(text, style=theme.style("fg_primary", bold=True))
        return bar
    out = Text("· ", style=theme.style("fg_faint"))
    out.append(text, style=theme.style("fg_secondary", bold=True))
    return out


def label(text: str, theme: Theme, *, tone: str = "fg_muted") -> Text:
    """UI label for nav and meta markers."""
    return Text(text.upper(), style=theme.style(tone))


def chip(text: str, theme: Theme, *, tone: str = "bg_raised") -> Text:
    """Inline chip: rounded-paren pill with a stepped background."""
    out = Text()
    out.append("(", style=theme.style("fg_faint", on=tone))
    out.append(text, style=theme.style("fg_primary", on=tone))
    out.append(")", style=theme.style("fg_faint", on=tone))
    return out


def inline_code(text: str, theme: Theme) -> Text:
    """Inline code span on a raised background chip."""
    return Text(f" {text} ", style=theme.style("accent_strong", on="bg_raised"))


def link_text(
    text: str, theme: Theme, *, href: str | None = None, state: str = "default"
) -> Text:
    """A link-styled text span, optionally with an OSC 8 target.

    Render states: default, hover, focus (visual-only for Phase 1/2 prep).
    """
    tone = "fg_link"
    bold = False
    if state == "hover":
        tone = "fg_link_hover"
    elif state == "focus":
        tone = "fg_link_hover"
        bold = True
    style = theme.style(tone, underline=True, bold=bold)
    if href:
        style = style + Style(link=href)
    return Text(text, style=style)


def strong(text: str, theme: Theme) -> Text:
    return Text(text, style=theme.style("fg_primary", bold=True))


def muted(text: str, theme: Theme) -> Text:
    return Text(text, style=theme.style("fg_muted"))


def italic(text: str, theme: Theme) -> Text:
    return Text(text, style=theme.style("fg_secondary", italic=True))


def strike(text: str, theme: Theme) -> Text:
    return Text(text, style=theme.style("fg_faint", strike=True))


def truncate(text: str, max_width: int, *, ellipsis: str = "…") -> str:
    """Truncate plain text to max_width cells, appending ellipsis if needed."""
    if max_width <= 0:
        return ""
    if len(text) <= max_width:
        return text
    if max_width <= len(ellipsis):
        return ellipsis[:max_width]
    return text[: max_width - len(ellipsis)] + ellipsis


def breadcrumb(items: list[str], theme: Theme, *, separator: str = " › ") -> Text:
    """A breadcrumb trail: muted separators, primary final segment."""
    out = Text()
    for index, item in enumerate(items):
        if index:
            out.append(separator, style=theme.style("fg_faint"))
        tone = "fg_primary" if index == len(items) - 1 else "fg_muted"
        out.append(item, style=theme.style(tone))
    return out


class Prose:
    """A wrapped body-text block.

    Renders prose wrapped to the available console width (or ``width``),
    using the fg scale so body text is never pure white.
    """

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        width: int | None = None,
        tone: str = "fg_secondary",
    ) -> None:
        self.text = text
        self.theme = theme
        self.width = width
        self.tone = tone

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = self.width or options.max_width
        text = Text(self.text, style=self.theme.style(self.tone))
        yield from text.wrap(console, width, overflow="fold", no_wrap=False)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> tuple[int, int]:
        width = self.width or options.max_width
        return min(20, width), width


def prose(
    text: str, theme: Theme, *, width: int | None = None, tone: str = "fg_secondary"
) -> Prose:
    """Convenience constructor for a wrapped prose block."""
    return Prose(text, theme, width=width, tone=tone)

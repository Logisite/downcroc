"""Code panel brick: chrome bar, line gutter, syntax-highlighted body."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from downcroc.cli.design.theme import Theme
from downcroc.cli.docs.clipboard import copy as copy_to_clipboard


class CodePanel:
    """A fenced code block as a floating card.

    Chrome bar (traffic dots, filename, copy hint) over a syntax-highlighted
    body with Pygments via rich Syntax; line numbers come from Syntax's own
    gutter, styled from tokens. Render is pure f(props, theme).
    """

    def __init__(
        self,
        source: str,
        theme: Theme,
        *,
        language: str = "python",
        filename: str = "",
        width: int | None = None,
        copied: bool = False,
        show_badge: bool = True,
        button_state: str = "default",
        highlight_lines: set[int] | None = None,
    ) -> None:
        self.source = source.rstrip("\n")
        self.theme = theme
        self.language = language
        self.filename = filename
        self.width = width
        self.copied = copied
        self.show_badge = show_badge
        self.button_state = button_state
        self.highlight_lines = highlight_lines or set()

    def copy(self) -> bool:
        """Copy the source to the clipboard and flip the button state."""
        ok = copy_to_clipboard(self.source)
        self.copied = ok
        self.button_state = "copied" if ok else "default"
        return ok

    def _button(self) -> Text:
        """The chrome copy button: renderable visual states."""
        theme = self.theme
        chrome = theme.bg("code_chrome_bg")
        out = Text(style=chrome)
        out.append(" ", style=chrome)
        state = "copied" if self.copied else self.button_state
        if state == "copied":
            out.append("copied ✓", style=theme.style("success", bold=True) + chrome)
        elif state == "disabled":
            out.append("[ copy ]", style=theme.style("fg_faint") + chrome)
        elif state == "hover" or state == "focus":
            out.append(
                "[ copy ]", style=theme.style("accent_strong", bold=True) + chrome
            )
        else:
            out.append(
                "[ copy ]", style=theme.style("code_button_fg", bold=True) + chrome
            )
        out.append(" ", style=chrome)
        return out

    def _chrome(self, width: int) -> Text:
        theme = self.theme
        chrome = theme.bg("code_chrome_bg")
        out = Text(style=chrome)
        out.append("  ", style=chrome)
        for dot, color in zip(range(3), (theme.danger, theme.warning, theme.success)):
            out.append("●", style=Style(color=color) + chrome)
            out.append(" ", style=chrome)
        if self.filename:
            out.append(" ", style=chrome)
            out.append(self.filename, style=theme.style("fg_secondary") + chrome)
        if self.show_badge and self.language:
            out.append("  ", style=chrome)
            out.append(
                f" {self.language} ",
                style=theme.style("fg_muted", on="bg_panel"),
            )
        button = self._button()
        gap = width - len(out) - len(button)
        if gap > 0:
            out.append(" " * gap, style=chrome)
        out.append_text(button)
        if len(out) < width:
            out.append(" " * (width - len(out)), style=chrome)
        return out

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        theme = self.theme
        width = min(self.width or options.max_width, options.max_width)
        yield self._chrome(width)
        syntax = Syntax(
            self.source,
            self.language or "text",
            theme="ansi_dark",
            word_wrap=False,
            background_color=theme.code_bg,
            line_numbers=True,
            indent_guides=True,
            highlight_lines=self.highlight_lines,
        )
        render_opts = options.update_width(width)
        for line in console.render_lines(
            syntax, render_opts, pad=True, new_lines=False
        ):
            yield from line
            yield Segment.line()
        yield Text(" " * width, style=theme.bg("code_bg"))


def sample_panel(theme: Theme) -> CodePanel:
    """A python sample for the gallery."""
    source = '''\
def stop(self, timeout: float = 5.0) -> None:
    """Stop the daemon and release its lock."""
    self._workers.stop(timeout=timeout)
    self._lock.release()
'''
    return CodePanel(
        source,
        theme,
        language="python",
        filename="runtime/service/lifecycle.py",
        width=72,
    )


def sample_shell(theme: Theme) -> CodePanel:
    """A bash sample for the gallery."""
    source = """\
uv run downcroc service start
uv run downcroc logs --event watcher. --json | grep '"level": 30'
"""
    return CodePanel(
        source,
        theme,
        language="bash",
        filename="deploy.sh",
        width=72,
    )

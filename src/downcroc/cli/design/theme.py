"""Design tokens for the downcroc design system.

Tokens are data. Bricks receive a Theme and never hardcode a color, spacing,
or character set, so the whole look is swappable by constructing another
Theme instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.style import Style


@dataclass(frozen=True)
class Theme:
    """Token sheet for the design system.

    PROPOSAL values, not locked. All colors are 24-bit hex so truecolor
    terminals get the intended look and Rich downgrades elsewhere.
    """

    name: str = "midnight"

    # elevation: page is the lowest step; raised sits on panel sits on page
    bg_page: str = "#000000"
    bg_panel: str = "#16161e"
    bg_raised: str = "#1f1f2a"
    bg_inset: str = "#0a0a10"

    # text: four steps, body text is never pure white
    fg_primary: str = "#c9d1d9"
    fg_secondary: str = "#8b949e"
    fg_muted: str = "#626c7a"
    fg_faint: str = "#3d4451"

    # one accent family, used sparingly: links, active markers, focus
    accent: str = "#7c6cf0"
    accent_dim: str = "#4c45a1"

    # semantic tones for callouts and status
    success: str = "#3fb950"
    warning: str = "#d29922"
    danger: str = "#f85149"
    info: str = "#58a6ff"

    # borders: alpha colors blend against whatever sits behind
    border_hairline: str = "#1e2330"
    border_focus: str = "#7c6cf0 45%"

    # spacing scale in cells
    space_1: int = 1
    space_2: int = 2
    space_3: int = 3
    space_4: int = 4
    space_6: int = 6
    space_8: int = 8

    # corner character set for cards and modals
    radius_s: str = "rounded"
    radius_m: str = "rounded"

    # panel chrome markers
    chrome_dot: str = "●"

    _style_cache: dict[str, Style] = field(
        default_factory=dict, compare=False, repr=False
    )

    def style(self, token: str, *, on: str | None = None, **attrs: bool) -> Style:
        """Build a Rich Style from tokens, cached per theme instance.

        ``theme.style("fg_primary")`` or ``theme.style("accent", bold=True)``.
        ``on`` takes another token name for a background color.
        """
        key = f"{token}/{on}/{attrs}"
        cached = self._style_cache.get(key)
        if cached is not None:
            return cached
        fg = getattr(self, token)
        style = Style(
            color=fg,
            bgcolor=getattr(self, on) if on else None,
            **attrs,
        )
        self._style_cache[key] = style
        return style

    def bg(self, token: str) -> Style:
        """A background-only style: the token becomes the cell background."""
        key = f"bg({token})"
        cached = self._style_cache.get(key)
        if cached is not None:
            return cached
        style = Style(bgcolor=getattr(self, token))
        self._style_cache[key] = style
        return style


DEFAULT = Theme()

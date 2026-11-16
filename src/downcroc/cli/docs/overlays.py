"""Overlay screens for docs: command palette/search, help (shadcn-mapped parts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from downcroc.cli.design.primitives.text import label
from downcroc.cli.design.theme import DEFAULT

# --- shadcn-mapped overlay/command component parts (TUI) ---


class DialogOverlay(Vertical):
    """Dialog overlay/scrim container."""


class DialogContent(Vertical):
    """Dialog content container."""


class DialogHeader(Vertical):
    """Dialog header."""


class DialogTitle(Static):
    """Dialog title."""


class DialogDescription(Static):
    """Dialog description."""


class CommandDialog(ModalScreen[object]):
    """shadcn CommandDialog (screen-level container)."""


class Command(Vertical):
    """shadcn Command root."""


class CommandInput(Input):
    """shadcn CommandInput."""


class CommandList(OptionList):
    """shadcn CommandList."""


class CommandGroup(Static):
    """shadcn CommandGroup heading/label (visual mapping in list)."""


class CommandItem(Static):
    """shadcn CommandItem (visual mapping)."""


class CommandEmpty(Static):
    """shadcn CommandEmpty."""


class CommandSeparator(Static):
    """shadcn CommandSeparator."""


@dataclass(frozen=True)
class PaletteItem:
    id: str
    title: str
    subtitle: str = ""
    kind: str = "page"  # page, heading, action
    payload: str = ""
    group: str = ""


class CommandPaletteScreen(CommandDialog):
    """Command/search palette overlay composed from shadcn-mapped parts."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss_none", "close"),
        Binding("ctrl+k", "dismiss_none", "close", show=False),
    ]

    DEFAULT_CSS = """
    CommandPaletteScreen { align: center top; background: #000000 65%; }
    DialogContent#dc-palette, #dc-palette {
        width: 88; max-width: 94%; height: 72%;
        margin-top: 3;
        background: #16161e;
        border: tall #343444;
        padding: 1 1;
    }
    DialogHeader#dc-palette-header { height: auto; padding: 0 0 1 0; }
    DialogTitle#dc-palette-title { color: #c9d1d9; }
    DialogDescription#dc-palette-desc { color: #8b949e; }
    CommandInput#dc-palette-input {
        margin: 0 0 1 0;
        background: #0a0a10;
        border: tall #232330;
        color: #c9d1d9;
    }
    CommandInput#dc-palette-input:focus { border: tall #7c6cf0; }
    CommandList#dc-palette-list { height: 1fr; background: transparent; border: none; }
    CommandEmpty#palette-empty { color: #8b949e; padding: 1 1; }
    """

    def __init__(
        self, items: list[PaletteItem], *, title: str = "Command Palette"
    ) -> None:
        super().__init__()
        self.items = list(items)
        self.filtered = list(items)
        self._title = title
        self._id_to_item: dict[str, PaletteItem] = {}

    def compose(self) -> ComposeResult:
        with DialogContent(id="dc-palette"), Command(id="dc-palette-command"):
            with DialogHeader(id="dc-palette-header"):
                yield DialogTitle(
                    label(self._title, DEFAULT, tone="fg_primary"),
                    id="dc-palette-title",
                )
                yield DialogDescription(
                    label(
                        "Search pages, headings, and actions",
                        DEFAULT,
                        tone="fg_faint",
                    ),
                    id="dc-palette-desc",
                )
            yield CommandInput(
                placeholder="Search pages, headings, and actions...",
                id="dc-palette-input",
            )
            yield CommandList(id="dc-palette-list")

    def on_mount(self) -> None:
        self._render_list("")
        self.query_one("#dc-palette-input", CommandInput).focus()

    def _render_list(self, query: str) -> None:
        q = query.strip().casefold()
        if q:
            words = [w for w in q.split() if w]
            filtered = []
            for item in self.items:
                hay = (
                    f"{item.title} {item.subtitle} {item.kind} {item.payload} {item.group}"
                ).casefold()
                if all(w in hay for w in words):
                    filtered.append(item)
            self.filtered = filtered[:120]
        else:
            self.filtered = self.items[:120]
        ol = self.query_one("#dc-palette-list", CommandList)
        ol.clear_options()
        self._id_to_item.clear()
        if not self.filtered:
            ol.add_option(Option("  No results", id=None, disabled=True))
            return

        group = None
        for i, item in enumerate(self.filtered):
            g = item.group or _default_group(item.kind)
            if g != group:
                group = g
                ol.add_option(Option(f"  {group.upper()}", id=None, disabled=True))
            text = item.title
            if item.subtitle and item.kind != "action":
                text = f"{item.title}  ·  {item.subtitle}"
            elif item.subtitle:
                text = f"{item.title}  —  {item.subtitle}"
            prefix = {"page": "↗", "heading": "#", "action": "⌘"}.get(item.kind, "·")
            oid = f"i-{i}"
            self._id_to_item[oid] = item
            ol.add_option(Option(f"    {prefix}  {text}", id=oid))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "palette-input":
            self._render_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "palette-input" and self.filtered:
            self.dismiss(self.filtered[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option.id:
            return
        item = self._id_to_item.get(event.option.id)
        if item is not None:
            self.dismiss(item)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


def _default_group(kind: str) -> str:
    if kind == "page":
        return "Pages"
    if kind == "heading":
        return "Headings"
    if kind == "action":
        return "Actions"
    return "Results"


class HelpDialogContent(DialogContent):
    """shadcn DialogContent for help."""


class HelpScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "close")]

    DEFAULT_CSS = """
    HelpScreen { align: center middle; background: #000000 65%; }
    HelpDialogContent#dc-help-box, #dc-help-box {
        width: 76; max-width: 94%; height: auto; max-height: 82%;
        background: #16161e; border: tall #343444; padding: 1 2;
        color: #c9d1d9;
    }
    DialogHeader#dc-help-header { height: auto; padding: 0 0 1 0; }
    """

    def compose(self) -> ComposeResult:
        lines = [
            "Navigation: sidebar/menu, Enter to open, [ / ] previous/next page",
            "Search/Commands: / or Ctrl+K opens command palette (pages, headings, actions)",
            "TOC: select a heading to jump (heuristic scroll) in current page",
            "Actions: c copy page, y copy link, o open in browser, r raw/source, e $EDITOR",
            "Layout: 5 zones — topbar, rail, article, outline/TOC, keybar/footer",
            "Close overlays: Esc   Quit: q",
        ]
        with HelpDialogContent(id="dc-help-box"):
            with DialogHeader(id="dc-help-header"):
                yield DialogTitle(
                    label("Docs Keybindings & Actions", DEFAULT, tone="fg_primary")
                )
                yield DialogDescription(
                    label(
                        "Keyboard, tap/focus, and action reference",
                        DEFAULT,
                        tone="fg_faint",
                    )
                )
            yield Static("\n".join(f"  • {line}" for line in lines))
            yield Static(label("\nPress Esc to close", DEFAULT, tone="fg_faint"))

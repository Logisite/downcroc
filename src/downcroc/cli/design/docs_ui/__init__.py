"""Docs UI scaffolding: stateful nav/toc, outline, sections, shell (Phase 3/4).

Split by responsibility (no god modules). Textual-aligned; no custom physics loops.
"""

from downcroc.cli.design.docs_ui.command import (
    CommandGroupSpec,
    CommandItemSpec,
    CommandPaletteSpec,
)
from downcroc.cli.design.docs_ui.nav import StatefulNavWidget
from downcroc.cli.design.docs_ui.outline import ContentOutlinePane
from downcroc.cli.design.docs_ui.pager import PagerLink, render_doc_pager
from downcroc.cli.design.docs_ui.sections import AnchoredSectionWidget
from downcroc.cli.design.docs_ui.shell import DocsShell
from downcroc.cli.design.docs_ui.sidebar import (
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupSpec,
    SidebarHeader,
    SidebarMenuItem,
    fill_sidebar_options,
)
from downcroc.cli.design.docs_ui.toc import StatefulTocWidget
from downcroc.cli.design.docs_ui.topbar import TopbarAction, render_topbar

__all__ = [
    "AnchoredSectionWidget",
    "CommandGroupSpec",
    "CommandItemSpec",
    "CommandPaletteSpec",
    "ContentOutlinePane",
    "DocsShell",
    "PagerLink",
    "SidebarContent",
    "SidebarFooter",
    "SidebarGroup",
    "SidebarGroupSpec",
    "SidebarHeader",
    "SidebarMenuItem",
    "StatefulNavWidget",
    "StatefulTocWidget",
    "TopbarAction",
    "fill_sidebar_options",
    "render_doc_pager",
    "render_topbar",
]

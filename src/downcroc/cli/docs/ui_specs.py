"""Build shadcn-mapped UI specs for docs sidebar and command palette."""

from __future__ import annotations

from downcroc.cli.design.docs_ui.command import CommandGroupSpec, CommandItemSpec
from downcroc.cli.design.docs_ui.sidebar import SidebarGroupSpec, SidebarMenuItem
from downcroc.cli.docs.nav_model import group_pages


def sidebar_groups(pages, *, active_route: str = "") -> list[SidebarGroupSpec]:
    groups = []
    for group in group_pages(pages):
        items = []
        for route, title, _rel in group.items:
            items.append(
                SidebarMenuItem(
                    title=title,
                    route=route,
                    active=(
                        route == active_route
                        or route == active_route.removesuffix(".md")
                    ),
                )
            )
        groups.append(
            SidebarGroupSpec(
                label=group.label,
                items=tuple(items),
                collapsible=bool(group.key),
                open=True,
            )
        )
    return groups


def command_groups(pages, *, headings_for_page) -> list[CommandGroupSpec]:
    page_items = []
    heading_items = []
    for p in pages:
        route = getattr(p, "route", "") or getattr(p, "rel", "").removesuffix(".md")
        if route == "index":
            route = ""
        rel = getattr(p, "rel", "")
        title = getattr(p, "title", rel)
        page_items.append(
            CommandItemSpec(
                id=route or rel,
                title=title,
                subtitle=rel,
                kind="page",
                payload=route or rel,
            )
        )
        for h in headings_for_page(p)[:16]:
            text = h if isinstance(h, str) else getattr(h, "text", "")
            slug = h if isinstance(h, str) else getattr(h, "slug", text)
            heading_items.append(
                CommandItemSpec(
                    id=f"{route}#{slug}",
                    title=str(text),
                    subtitle=title,
                    kind="heading",
                    payload=f"{route}#{slug}",
                )
            )
    actions = [
        CommandItemSpec(
            "action:copy",
            "Copy page markdown",
            "Copy current page source",
            kind="action",
            payload="action:copy",
        ),
        CommandItemSpec(
            "action:copy-link",
            "Copy page link",
            "Copy docs route/link for this page",
            kind="action",
            payload="action:copy-link",
        ),
        CommandItemSpec(
            "action:copy-heading-link",
            "Copy heading link",
            "Copy link to selected/first heading",
            kind="action",
            payload="action:copy-heading-link",
        ),
        CommandItemSpec(
            "action:open",
            "Open in browser",
            "Open source file URI",
            kind="action",
            payload="action:open",
        ),
        CommandItemSpec(
            "action:raw",
            "Toggle raw/source view",
            "Show markdown source",
            kind="action",
            payload="action:raw",
        ),
        CommandItemSpec(
            "action:edit",
            "Open in $EDITOR",
            "Edit current page in editor",
            kind="action",
            payload="action:edit",
        ),
        CommandItemSpec(
            "action:help",
            "Show help",
            "Keybindings and actions",
            kind="action",
            payload="action:help",
        ),
    ]
    groups = [CommandGroupSpec("Pages", tuple(page_items))]
    if heading_items:
        groups.append(CommandGroupSpec("Headings", tuple(heading_items[:200])))
    groups.append(CommandGroupSpec("Actions", tuple(actions)))
    return groups

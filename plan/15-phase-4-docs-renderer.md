# Phase 4 — Docs renderer and app integration

Status: in progress (Phase 4). Builds on completed Phase 1–3 design primitives/composites and docs UI scaffolds in `src/downcroc/cli/design/*`.

## Goal

Replace and integrate the current terminal docs experience (`src/downcroc/cli/docs/*`) with a typed markdown pipeline and a 5-zone docs shell composed from the design system:

- markdown-it-py parsing → typed block/AST model → block-to-primitive renderer map
- Rich/Textual 5-zone shell (rail | article | TOC | topbar | keybar) with TCSS layout
- TOC scroll-spy, anchors, routing/navigation, breadcrumbs, previous/next pager
- search, command palette, overlays/dimming, copy/open actions, and `$EDITOR` integration hooks
- real docs/content loading from the packaged docs tree

No domain coupling in `cli/design/paint|interaction|primitives`. Docs-specific wiring lives in `cli/docs` and docs-facing design scaffolds/composites as appropriate.

## Component architecture (shadcn-inspired mapping → TUI/Textual)

This tree is the target composition. “shadcn part” names indicate the role/pattern; implementation uses Textual widgets/containers + Rich renderables and downcroc design primitives/composites.

```text
DocsApp (Textual App)
├─ Providers / global services (app-level)
│  ├─ ThemeProvider        -> downcroc docs theme + design Theme tokens
│  ├─ TooltipProvider      -> tooltip/help hint behavior (where supported)
│  ├─ Router/DocState      -> current route/doc, history, anchor target
│  ├─ SearchIndex          -> indexed pages/headings/blocks
│  ├─ Toaster              -> toast/notification surface (copy, errors, status)
│  └─ CommandPalette       -> global command/search overlay (open/toggle)
│
├─ Shell (5-zone layout, TCSS)
│  ├─ TopBar (zone)
│  │  ├─ SidebarTrigger    -> Button (toggle rail)
│  │  ├─ Separator
│  │  ├─ Breadcrumb        -> BreadcrumbList > Item/Link/Separator/Page(+Ellipsis)
│  │  └─ TopbarActions
│  │     ├─ Button         -> search / open command palette
│  │     ├─ Button         -> copy page/link
│  │     ├─ DropdownMenu   -> page actions (open in $EDITOR, raw/source, copy)
│  │     └─ Button         -> theme/view toggle (as applicable)
│  │
│  ├─ Body (ResizablePanelGroup direction=horizontal)
│  │  ├─ RailPanel (ResizablePanel)  [left rail]
│  │  │  └─ Sidebar
│  │  │     ├─ SidebarHeader       -> title/home
│  │  │     ├─ SidebarContent
│  │  │     │  └─ SidebarGroup*
│  │  │     │     ├─ SidebarGroupLabel
│  │  │     │     └─ SidebarMenu
│  │  │     │        ├─ SidebarMenuItem* (leaf) -> SidebarMenuButton/Link
│  │  │     │        └─ Collapsible* (nested)
│  │  │     │           ├─ CollapsibleTrigger -> SidebarMenuButton
│  │  │     │           └─ CollapsibleContent -> SidebarMenuSub > SubItem/SubButton*
│  │  │     └─ SidebarFooter       -> meta/version (optional)
│  │  │
│  │  ├─ ResizableHandle
│  │  │
│  │  ├─ ArticlePanel (ResizablePanel)  [main article]
│  │  │  └─ ScrollArea (doc viewport, scroll-spy source)
│  │  │     └─ Article
│  │  │        ├─ DocHeader
│  │  │        │  ├─ TypographyH1 (title)
│  │  │        │  ├─ TypographyLead/Muted (description)
│  │  │        │  └─ MetaRow/Badges + Separator
│  │  │        │
│  │  │        ├─ DocContent (typed block renderers)
│  │  │        │  ├─ HeadingBlock* (h1-h6, anchored)
│  │  │        │  │  ├─ TypographyHeading(id=slug)
│  │  │        │  │  └─ Button(icon, ghost) + Tooltip  [copy link]
│  │  │        │  ├─ ParagraphBlock* -> TypographyP with inline runs
│  │  │        │  │  ├─ text / strong / em / strike
│  │  │        │  │  ├─ InlineCode / Badge
│  │  │        │  │  └─ Link (internal route or external)
│  │  │        │  ├─ BlockquoteBlock* / CalloutBlock*
│  │  │        │  │  └─ Alert (AlertTitle + AlertDescription) or styled quote
│  │  │        │  ├─ ListBlock* (ul/ol/task, nested)
│  │  │        │  │  └─ ListItem* (+ Checkbox for task items)
│  │  │        │  ├─ CodeBlock*
│  │  │        │  │  └─ Card
│  │  │        │  │     ├─ CodeHeader (Badge lang + Button copy + Tooltip)
│  │  │        │  │     └─ ScrollArea/Preformatted highlighted code
│  │  │        │  ├─ TableBlock*
│  │  │        │  │  └─ Table (Header/Body/Row/Head/Cell/Caption) in ScrollArea
│  │  │        │  ├─ FigureBlock* / ImageBlock*
│  │  │        │  │  └─ Figure (AspectRatio/media + Caption TypographyMuted)
│  │  │        │  ├─ TabsBlock* / CollapsibleBlock* (extension/directive, optional)
│  │  │        │  ├─ Separator (hr)
│  │  │        │  └─ Frontmatter/Meta/Footnotes blocks as applicable
│  │  │        │
│  │  │        └─ DocFooter
│  │  │           ├─ Separator
│  │  │           └─ Pager (Pagination)
│  │  │              ├─ Button/Link previous (label + route/target)
│  │  │              └─ Button/Link next (label + route/target)
│  │  │
│  │  ├─ ResizableHandle
│  │  │
│  │  └─ TocPanel (ResizablePanel)  [right outline]
│  │     └─ ScrollArea
│  │        └─ Toc ("On this page")
│  │           └─ TocList > TocItem* (nested levels, active via scroll-spy)
│  │
│  └─ Keybar/Footer (zone)
│     ├─ Separator
│     └─ Key hints / status (Badge/Kbd-style + muted text)
│
└─ Overlays
   ├─ CommandDialog        -> CommandInput/List/Group/Item/Empty/Separator
   ├─ Dialog / Sheet       -> modal surfaces as needed
   ├─ DropdownMenu / Popover / Tooltip
   └─ Toast notifications
```

## Data/wiring flow

```text
docs root (packaged/checkout)
  -> content loader/index (pages, frontmatter/meta, routes/slugs, nav tree, prev/next)
  -> markdown-it-py parse (per page)
  -> typed block/inline AST model (normalized nodes)
  -> renderer registry (node kind -> design primitive/component renderer)
  -> Article renderables + heading index (ids/slugs/levels/text)
  -> Shell state: route, current page, nav active, breadcrumb, pager, toc items
  -> Scroll-spy/anchors: viewport position <-> active heading/toc/anchor
  -> Search index: page/title/heading/body text -> query results
  -> Actions: navigate, open palette, copy link/page, open in $EDITOR, raw/source
```

## Implementation slices (Phase 4)

1. **Content model + parsing**
   - Add markdown-it-py dependency (uv add).
   - Implement typed block/inline model and parser (`cli/docs/content/` or `cli/docs/model_v2`): frontmatter/meta, headings with slugs/ids, blocks (heading, paragraph, blockquote/callout, list/task, code fence, table, hr, image/figure, html passthrough policy), inline nodes (text, strong, em, code, link, image).
   - Build page index: routes/slugs, nav tree/order, prev/next, heading index.
   - Tests: parse representative docs fixtures (in-package) and assert model.

2. **Renderer mapping to design system**
   - Create renderer registry mapping typed nodes -> Rich renderables using `cli/design` primitives/composites (text/prose/heading, inline code/link/badge, callout, list, code panel, table, figure, rule/separator, key-value/meta) and new primitives as needed.
   - Replace `cli/docs/render.py` rendering path to consume typed model + new renderers (keep CLI/raw behavior working).
   - Snapshot/golden coverage for key block types.

3. **5-zone shell + TCSS layout**
   - Build Textual docs shell with zones (topbar/breadcrumb/actions, sidebar rail, article ScrollArea, TOC outline, keybar/footer) using design tokens/components and TCSS for layout.
   - Responsive behavior (collapse rail/toc by width), focus/keyboard navigation.
   - Integrate into `cli/docs/app.py` and `downcroc docs` interactive flow.

4. **Navigation, anchors, TOC scroll-spy, pager**
   - Route/page selection wired to sidebar, breadcrumb, pager (prev/next), and content viewport.
   - Anchor/slug generation + copy-link action; scroll-to-anchor; scroll-spy updates active TOC/section.

5. **Search, command palette, overlays, actions**
   - Search index and UI (filter/jump/results); command palette (navigate/jump/actions).
   - Overlays/dimming patterns; toasts for copy/status/errors.
   - Actions: copy page/link, open in browser/raw, `$EDITOR` hook (where supported).

6. **Integration hardening**
   - Replace legacy rendering/theme/blocks where superseded; keep `--raw/--open/--list/--search` CLI modes correct.
   - Verification: ruff/format/check, compileall, targeted pytest slices + black-box acceptance as applicable, manual/docs shots where useful.
   - Update plan/docs notes for behavior changes.

## Current state / known gaps

- Existing: `cli/docs/{app,render,model,blocks,search,theme,clipboard}.py` with basic parsing, Rich Markdown rendering, simple Textual layout, list/search/open/copy/raw.
- Missing/incomplete for Phase 4: markdown-it-py typed AST model, full renderer registry on design primitives, TCSS 5-zone shell, real scroll-spy/anchors/routing, command palette, overlays, robust search/index, `$EDITOR`/copy-link integration, and full replacement of legacy rendering paths.

## Review loop

Per significant slice: implement -> `uv run ruff check --fix src tests && uv run ruff format src tests && uv run ruff check src tests && uv run python -m compileall -q src` -> targeted tests (`uv run pytest -q ...`) -> run/docs shot/manual verification where relevant -> critique -> commit. Keep files focused and split by responsibility (<400 lines where practical).

## Reference: shadcn-mapped DOM tree (target composition)

```text
DocsRendererApp (root DOM/component tree, shadcn parts -> TUI mapping)
├── ThemeProvider
│   └── TooltipProvider
│       └── RouterProvider (route/doc state)
│           ├── Toaster (Sonner)  [global feedback]
│           ├── CommandDialog  [global palette/search]
│           │   ├── CommandInput
│           │   └── CommandList
│           │       ├── CommandEmpty
│           │       ├── CommandGroup "Pages"
│           │       │   └── CommandItem* (navigate route/page)
│           │       ├── CommandSeparator
│           │       └── CommandGroup "Headings / Actions"
│           │           └── CommandItem* (jump anchor, copy link, open in $EDITOR)
│           │
│           └── SidebarProvider (shell state)
│               └── div.app-shell (5-zone layout)
│                   ├── header.topbar
│                   │   ├── SidebarTrigger (Button)
│                   │   ├── Separator (vertical)
│                   │   ├── Breadcrumb
│                   │   │   └── BreadcrumbList
│                   │   │       ├── BreadcrumbItem -> BreadcrumbLink (route/parent)
│                   │   │       ├── BreadcrumbSeparator
│                   │   │       ├── BreadcrumbItem -> BreadcrumbEllipsis (optional)
│                   │   │       ├── BreadcrumbSeparator
│                   │   │       └── BreadcrumbItem -> BreadcrumbPage (current)
│                   │   └── div.topbar-actions
│                   │       ├── Button (search / open CommandDialog)
│                   │       ├── Button (copy page/link)
│                   │       ├── DropdownMenu (page actions)
│                   │       │   ├── DropdownMenuTrigger -> Button(icon)
│                   │       │   └── DropdownMenuContent
│                   │       │       ├── DropdownMenuItem "Open in $EDITOR"
│                   │       │       ├── DropdownMenuItem "Copy link"
│                   │       │       └── DropdownMenuItem "View source/raw"
│                   │       └── Button (theme toggle)
│                   │
│                   ├── div.body
│                   │   └── ResizablePanelGroup (horizontal)
│                   │       ├── ResizablePanel [left rail / sidebar nav]
│                   │       │   └── Sidebar (collapsible)
│                   │       │       ├── SidebarHeader -> SidebarMenu > MenuItem/Button (home)
│                   │       │       ├── SidebarContent
│                   │       │       │   └── SidebarGroup*
│                   │       │       │       ├── SidebarGroupLabel
│                   │       │       │       └── SidebarGroupContent
│                   │       │       │           └── SidebarMenu
│                   │       │       │               ├── SidebarMenuItem* -> SidebarMenuButton/Link
│                   │       │       │               └── Collapsible* (nested)
│                   │       │       │                   ├── CollapsibleTrigger -> SidebarMenuButton
│                   │       │       │                   └── CollapsibleContent -> SidebarMenuSub > SubItem/SubButton*
│                   │       │       └── SidebarFooter (optional)
│                   │       ├── ResizableHandle
│                   │       ├── ResizablePanel [article / main content]
│                   │       │   └── ScrollArea (viewport, scroll-spy source)
│                   │       │       └── main.article
│                   │       │           ├── article.doc-header
│                   │       │           │   ├── TypographyH1 (title)
│                   │       │           │   ├── TypographyLead (description)
│                   │       │           │   └── div.meta-row -> Badge* + Separator
│                   │       │           ├── section.doc-content (typed block renderers)
│                   │       │           │   ├── HeadingBlock* -> TypographyHn(id) + Tooltip/Button(copy link)
│                   │       │           │   ├── ParagraphBlock* -> TypographyP (inline runs, Link, InlineCode)
│                   │       │           │   ├── Blockquote/CalloutBlock* -> Alert(AlertTitle,AlertDescription)
│                   │       │           │   ├── ListBlock* -> ul/ol/li* (+ Checkbox for tasks)
│                   │       │           │   ├── CodeBlock* -> Card(Header: Badge lang + copy Button, Body: pre/code)
│                   │       │           │   ├── TableBlock* -> Table(Header/Body/Row/Head/Cell/Caption)
│                   │       │           │   ├── FigureBlock* -> figure(AspectRatio/img + figcaption)
│                   │       │           │   ├── TabsBlock*/CollapsibleBlock* (extensions)
│                   │       │           │   └── Separator (hr)
│                   │       │           └── footer.doc-footer
│                   │       │               ├── Separator
│                   │       │               └── nav.pager -> Button/Link previous + Button/Link next
│                   │       ├── ResizableHandle
│                   │       └── ResizablePanel [right outline / TOC]
│                   │           └── ScrollArea
│                   │               └── aside.toc
│                   │                   ├── TypographySmall "On this page"
│                   │                   └── TocList -> TocItem* (nested, active via scroll-spy)
│                   │
│                   └── footer.statusbar (key hints/status)
│                       ├── Separator
│                       └── hints -> Badge/Kbd-style + TypographyMuted
```

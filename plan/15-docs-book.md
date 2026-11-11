# 15 - Documentation book and terminal delivery

The product has one documentation book. The browser and the terminal are two renderers over the
same Markdown. Neither renderer owns content that the other cannot express.

`rich`, `markdown-it-py`, and `pygments` are already runtime dependencies. The terminal renderer
uses them. The browser renderer uses MkDocs Material with pymdown extensions and a small custom
theme.

## Goals

- One source tree, two polished surfaces.
- Modern browser docs: sidebar, command-palette search, dark mode, copy buttons, tabs, callouts,
  keyboard navigation, breadcrumbs, right-hand TOC, and a version badge.
- Precise terminal docs: real headings, code panels, callouts, tables, paging, search, and a
  readable layout at 40, 80, and 120 columns.
- The book is packaged in the wheel and works offline.
- The same book deploys to GitHub Pages.
- `downcroc help` remains the short terminal path. The book is the long-form reference.
- Every claim, command, config key, event, and API field has one source of truth.

## Source layout

```text
docs/
  index.md
  getting-started/
    install.md
    first-run.md
    connect-a-mailbox.md
    first-campaign.md
  concepts/
    architecture.md
    vault.md
    accounts.md
    batches.md
    jobs.md
    attempts.md
    holds.md
    smtp-seats.md
    followups.md
    threading.md
  operations/
    service.md
    logs.md
    doctor.md
    backup.md
    restore.md
    retention.md
    capacity.md
  cli/
    index.md
    accounts.md
    batches.md
    jobs.md
    followups.md
    mail.md
    stats.md
    config.md
    logs.md
    service.md
  reference/
    campaign-schema.md
    template-schema.md
    config.md
    events.md
    api.md
    exit-codes.md
  security/
    model.md
    vault.md
    api.md
    hardening.md
  troubleshooting/
    index.md
    vault.md
    accounts.md
    inbound.md
    outbound.md
    followups.md
  release-notes/
    index.md
  assets/
    styles.css
    palette.css
    logo.svg
    og.png
  mkdocs.yml
```

The source tree is copied into the wheel as `downcroc/docs/`. The built site is never required at
runtime. `downcroc docs --open` opens the installed copy, not the network.

## Page frontmatter

Every page starts with YAML frontmatter:

```yaml
---
title: SMTP seats
description: How seats, rotation, and API fallback work.
tags: [smtp, seats, capacity, dispatch]
audience: operator
status: stable
since: 1.3.1
updated: 2026-11-11
order: 35
related:
  - concepts/capacity.md
  - operations/doctor.md
terminal:
  summary: Seats are transport reservations, not account status.
  max_width: 100
  toc: true
search_boost: 1.2
---
```

Rules:

- `title` is required and matches the first `#` heading.
- `description` is required and is used by the browser meta tags and terminal search.
- `audience` is `user`, `operator`, `developer`, or `security`.
- `status` is `draft`, `stable`, `deprecated`, or `internal`.
- `since` is the first release that shipped the behavior.
- `order` controls navigation inside a section.
- `related` is a list of relative page paths.
- `terminal.summary` is the one-line result shown by `downcroc docs --list`.
- `terminal.max_width` caps prose width for dense pages. Code is never narrowed.
- `terminal.toc` controls whether a page prints an inline table of contents.
- `search_boost` tunes local ranking only. It never affects browser search.

Unknown keys are an error in CI.

## Content blocks

Use standard Markdown plus MkDocs Material extensions. The terminal renderer must degrade every
block gracefully.

| Block | Browser | Terminal |
|---|---|---|
| Heading | anchor, TOC, permalink | accent heading, underline for H1/H2 |
| Paragraph | typography, max measure | wrapped prose, no box |
| Bullet list | styled marker | glyph marker, hanging indent |
| Ordered list | numbered | numbered, aligned dot |
| Task list | checkbox | `[x]` / `[ ]` |
| Inline code | subtle chip | muted colour |
| Code fence | syntax highlight, copy button | Pygments panel, no copy button |
| Admonition | Material callout | left rule plus label |
| Tab group | tabs | stacked with bold tab labels |
| Table | responsive table | Rich table if it fits, otherwise key/value rows |
| Details | disclosure | `summary` then indented body |
| Footnote | linked note | collected at the end |
| Mermaid | rendered diagram | alt text plus target URL |
| Image | responsive image, caption | alt text plus path or URL |
| Keyboard | key caps | `<key>` text |
| Steps | numbered cards | numbered lines with hanging indent |
| Cards | link cards | label, summary, path |

Supported admonition types:

```markdown
!!! note "Before you start"
!!! tip "Shortcut"
!!! warning "This changes data"
!!! danger "Irreversible"
!!! example "Working command"
!!! quote "From the design"
```

The terminal maps `note` and `example` to the normal accent, `tip` to green, `warning` to yellow,
and `danger` to red. It never prints the `!!!` syntax.

## Navigation schema

The browser sidebar follows the directory tree, then `order`, then `title`.

Top-level order:

1. Getting started
2. Concepts
3. Operations
4. CLI
5. Reference
6. Security
7. Troubleshooting
8. Release notes

The terminal uses the same order. `downcroc docs --list` prints a two-column tree: section and
page summary. `--json` returns the same tree as records.

## Terminal renderer

Command surface:

```sh
downcroc docs --list
downcroc docs --list --json
downcroc docs smtp-seats
downcroc docs concepts/smtp-seats
downcroc docs --search "seat failover"
downcroc docs smtp-seats --raw
downcroc docs smtp-seats --no-pager
downcroc docs smtp-seats --width 80
downcroc docs --open
```

Resolution order:

1. Exact relative path.
2. Exact slug.
3. Unique title match.
4. Tag match with one result.
5. Ambiguous match prints candidates and exits 2.
6. No match suggests `--search`.

Rendering rules:

- Use `rich.console.Console` with `soft_wrap=False`, the detected width, and `NO_COLOR` respected.
- Use `rich.markdown.Markdown` for prose, lists, quotes, and inline formatting.
- Use `rich.syntax.Syntax` for fenced code, with the language from the fence when present.
- Use `rich.panel.Panel` only for terminal transcripts and destructive examples, never for every
  paragraph.
- Use `rich.table.Table` for tables that fit the content width. Otherwise render the header as a
  bold line and each row as a stacked `key: value` block.
- Use `rich.pager.pager` when the output is taller than the terminal and paging is enabled.
- Use `rich.text.Text` for keyboard keys and links. A link prints as `label <url>` when the
  terminal cannot hyperlink.
- Use `rich.markdown.Markdown` heading callbacks to keep the page TOC in sync.
- Use `rich.progress` only for `--build`, never for reading a page.
- Use `rich.live` only in the interactive docs browser, never in non-interactive output.

Widths:

- 40 columns: one column, no side-by-side tables, code wraps at soft boundaries.
- 80 columns: standard layout, tables fit only when narrow.
- 120 columns: prose capped at `terminal.max_width`, code uses the full width.
- Wider than 160: prose stays capped, navigation moves to a left rail in the interactive browser.

Interactive browser:

```text
downcroc docs
```

- Left rail: sections and pages.
- Main pane: rendered page.
- Right rail: page TOC when width allows.
- `/` opens search, `enter` opens, `esc` back, `?` help, `q` quit.
- `o` opens the same page in the browser.
- `r` toggles raw Markdown.
- The frame redraws in place with the existing `Frame` discipline. No bare newline drift.
- Cursor is hidden while the frame redraws and shown while a search field is focused.

Non-interactive output has no cursor movement, no live region, and no colour when piped.

## Browser renderer

MkDocs Material with:

- `navigation.tabs`, `navigation.sections`, `navigation.indexes`, `navigation.top`
- `toc.follow`, `toc.integrate`
- `search.suggest`, `search.highlight`, `search.share`
- `content.code.copy`, `content.code.annotate`, `content.tabs.link`
- `palette` with a light and dark scheme and a system preference default
- `pymdownx.highlight`, `superfences`, `tabbed`, `details`, `admonition`, `footnotes`, `keys`
- `pymdownx.arithmatex` only if a page needs it
- `mkdocs-minify-plugin`
- `mkdocs-git-revision-date-localized-plugin`
- `mkdocs-redirects` for moved pages
- one custom stylesheet and one small JS file, no framework

Design rules:

- Max prose measure of 72 characters.
- One accent colour plus semantic success, warning, and danger tones.
- Sticky header, collapsible sidebar, right TOC, breadcrumbs, previous and next links.
- Command palette opens with `Ctrl+K` and `/`.
- Code blocks have language labels, copy buttons, and line anchors.
- Tables scroll horizontally rather than shrinking text.
- Dark mode is a real palette, not an inverted stylesheet.
- Images use explicit width and height to avoid layout shift.
- Every page has `description`, canonical URL, and Open Graph tags.
- The 404 page links to search, getting started, and troubleshooting.
- No cookies, analytics, or third-party fonts by default.

## Search schema

Browser search is MkDocs built-in search.

Terminal search is offline and prebuilt:

```json
{
  "page": "concepts/smtp-seats.md",
  "title": "SMTP seats",
  "summary": "Seats are transport reservations, not account status.",
  "tags": ["smtp", "seats", "capacity"],
  "headings": ["How a seat is elected", "Failover", "API fallback"],
  "body": "normalized searchable text"
}
```

Ranking order:

1. Exact title.
2. Title prefix.
3. Heading match.
4. Tag match.
5. Body match.
6. `search_boost` tie-break.

Results show title, section, summary, and the matching line. `--json` returns records with page,
title, section, line, and score.

## Build schema

Development:

```sh
uv run downcroc docs --list
uv run mkdocs serve
```

Build:

```sh
uv run mkdocs build --strict
```

CI:

1. Markdown lint.
2. Frontmatter schema validation.
3. Link check, including relative links and anchors.
4. Build the browser site with `--strict`.
5. Build the terminal search index.
6. Run the terminal golden renders at 40, 80, and 120 columns.
7. Assert every CLI command, flag, config key, event, and error code appears in reference.
8. Run every fenced `sh` example that is marked `run`.
9. Package `docs/` and the built site in the wheel.
10. Deploy the same built site to GitHub Pages from the main branch.

## Packaging

- Source Markdown lives in `docs/`.
- The wheel contains `downcroc/docs/` with the source tree and the search index.
- `downcroc docs --open` opens the installed `index.html` if present, otherwise the Markdown
  index through the terminal renderer.
- No documentation build tool is a runtime dependency. MkDocs lives in a `docs` dependency group.
- The wheel remains usable offline.
- The browser site is a release artifact and is also deployed to Pages.

## Tests

- Every page has valid frontmatter.
- Every relative link and anchor resolves.
- Every page title is unique.
- Every CLI command and flag is documented.
- Every config key and event is documented.
- Terminal output at 40 columns has no line wider than the terminal.
- Terminal output with `NO_COLOR=1` has no ANSI escapes.
- `--raw` equals the source file bytes.
- `--json --list` is valid JSON records.
- Search finds a page by title, tag, heading, and body.
- Ambiguous topics exit 2 and name the candidates.
- Browser build is strict and has no broken internal links.
- Browser pages have description, canonical URL, and a single H1.
- The 404 page is present.
- Accessibility: landmarks, skip link, focus states, and contrast are checked by a small audit.

## Versioning

- `docs/` documents the current release.
- `release-notes/` is immutable history.
- A page may declare `since` and `status`.
- Deprecated behavior stays documented until the next major release.
- The browser shows the current version from package metadata.
- No version selector until the project publishes more than one maintained line.

## Writing rules

- Lead with the outcome, then the steps.
- Use second person and active voice.
- One idea per paragraph.
- Commands are copy-paste complete.
- Every warning names the consequence and the recovery.
- Every error code names the next action.
- No screenshots for text that can be copied.
- No marketing adjectives in reference pages.
- No credentials, tokens, or real addresses in examples.
- No em dashes.

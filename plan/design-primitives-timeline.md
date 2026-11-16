# downcroc design system: primitives-first development timeline

Detailed plan for building the design system brick by brick, starting from
primitives. This supersedes the premature markdown/docs-rendering direction:
we are **not** integrating markdown parsing, block models, shell/layout, or
real docs loading yet. We build and prove primitives first.

## Ground rules

- **Primitives-first:** every brick is a pure renderable `f(props, theme)`
  (Rich segments/canvas) with a clear contract, variants, and states.
- **No hardcoded external paths/content** in `cli/design/` or the gallery.
  Samples and fixtures live as in-package data/factories (code-defined), never
  as paths to repo docs or other external content.
- **No domain coupling:** `paint/`, `interaction/`, and `primitives/` know
  nothing about docs, pages, downcroc domain objects, or the docs app.
- **Theme is data:** bricks read tokens from an injected `Theme`; no
  hardcoded colors/spacing in bricks.
- **Visual identity in Rich; layout later in TCSS:** primitives paint their
  own faces; TCSS is reserved for shell/layout composition in a deferred phase.
- **Subpixel/Braille/shape rasterizers are considered, not scheduled:** add
  only when a concrete primitive needs them.
- **Review loop per slice:** in-package samples → gallery → SVG/PNG snapshot
  review → snapshot tests → commit. Leave the codebase better each slice.

## Current baseline

| Area | Exists now | Gaps |
|---|---|---|
| `theme.py` | Basic token dataclass, `style()`, `bg()`, default theme | Full token contract, state/overlay/motion tokens, helper methods, token-sheet gallery |
| `paint/canvas.py` | `set`, `fill`, `fill_rect`, `hline`, `rounded_rect` | `vline`, inner/padded rect helpers, safe clipping helpers |
| `paint/color.py` | `blend`, `gradient`, `fade_block`, span helper | tint/overlay helpers for states, contrast-safe utilities |
| `primitives/text.py` | `heading(h1/h2)`, `label`, `chip`, `prose` (basic) | h3, wrapped prose block, link, inline code in flow, emphasis helpers, breadcrumb/label variants, truncation |
| `primitives/card.py` | borderless + hairline stepped card | slots/padding props, variants, proper measure/wrap, state hooks |
| `primitives/code_panel.py` | chrome+dots+filename+button, Syntax body, `.copy()` | pinned/right-aligned chrome, width consistency, language badge, rendered states (hover/copied/disabled), hit-target contract |
| `primitives/keybar.py` | `keybar`, `keycap` | groups/separators, variants, disabled/muted states |
| `primitives/rule.py` | hairline, divider | spacing props, labeled/variant options |
| `primitives/callout.py` | accent bar + title/body, tone map | icon slot, full tone set, compact/padding variants, rich body slot |
| `primitives/table_view.py` | restyled Rich table | header band control, zebra, alignment/overflow, compact, empty/row-state hooks |
| `interaction/` | not present | full layer missing |
| Gallery/tests | static samples, SVG/PNG export, snapshots | per-primitive variant/state sections, sample factories |

## Directory structure (illustrative, ASCII tree)

```text
src/downcroc/cli/design/
├── __init__.py                 # public exports (curated)
├── theme.py                    # Theme dataclass, token sheet, helpers
├── gallery.py                  # headless gallery render/export (samples only)
├── playground.py               # live Textual review app
├── samples/                    # in-package sample factories/fixtures (add as needed)
│   ├── __init__.py
│   ├── text_samples.py
│   ├── surface_samples.py
│   ├── code_samples.py
│   ├── data_samples.py
│   └── feedback_samples.py
├── paint/
│   ├── __init__.py
│   ├── canvas.py               # CellCanvas: fill/rect/line/rounded/border helpers
│   ├── color.py                # blend, tint, gradient, alpha/overlay helpers
│   └── measure.py              # wrap/measure helpers (if needed)
├── interaction/                # Phase 2: pointer/gesture/state contracts
│   ├── __init__.py
│   ├── pointer.py              # normalized pointer events
│   ├── hit.py                  # hit regions for painted areas
│   ├── hover.py                # hover enter/exit + transitions
│   ├── focus.py                # focus ring state (separate from hover)
│   ├── gestures.py             # tap/double-tap/long-press/drag/swipe
│   ├── actions.py              # bubbled messages (Tapped, Hovered, Copied, ...)
│   ├── state.py                # interaction state enums + style mapping
│   └── scroll_physics.py       # inertial/smooth/anchor helpers (scoped)
├── primitives/
│   ├── __init__.py
│   ├── text.py                 # heading, prose block, label, emphasis, truncate
│   ├── inline.py               # link, inline_code, badge, kbd/keycap-inline
│   ├── breadcrumb.py           # breadcrumb trail
│   ├── rule.py                 # hairline, divider, spacer
│   ├── icon.py                 # Nerd Font glyph registry + status dot
│   ├── card.py                 # card/panel/inset surfaces
│   ├── blockquote.py           # quote block
│   ├── callout.py              # semantic callouts/admonitions
│   ├── code_panel.py           # fenced code chrome + syntax body
│   ├── table_view.py           # table rendering/styling
│   ├── list_block.py           # ul/ol/task lists + list items
│   ├── key_value.py            # definition/meta rows, empty state
│   ├── keybar.py               # keybar + keycap
│   ├── button.py               # action/button atom (visual states)
│   ├── toast.py                # toast/pill feedback
│   └── nav.py                  # nav_item, toc_item, tag/chip list (visual atoms)
├── components/                 # Phase 3: compositions of primitives (no domain)
│   └── __init__.py
└── layout/                     # Phase 4 (deferred): shell/zones/TCSS composition
    └── __init__.py

scripts/
└── design/
    └── shot.py                 # gallery -> SVG/PNG -> review outbox

tests/
└── cli/
    └── design/
        ├── __init__.py
        ├── test_design_bricks.py
        └── __snapshots__/...
```

**Explicit note:** this tree is **illustrative, not a limit**. Modules may be
added, split, renamed, regrouped, or promoted as the build evolves (e.g.
`primitives/text/` package instead of files, extra paint helpers, dedicated
state/render adapters, sample modules). The build is **not limited** to the
directories or files listed above; follow the contracts and phase goals, not a
fixed file map.

## Phase 0 — Substrate hardening

### 0.1 Token sheet (expand `theme.py`)
| Token group | Tokens | Purpose |
|---|---|---|
| Background / elevation | `bg_page`, `bg_panel`, `bg_raised`, `bg_inset`, `bg_overlay`, `bg_hover`, `bg_active`, `bg_selected` | Stepped fills as primary material; state layers |
| Foreground / text | `fg_primary`, `fg_secondary`, `fg_muted`, `fg_faint`, `fg_inverse`, `fg_link`, `fg_link_hover` | Hierarchy; body never pure white |
| Accent / brand | `accent`, `accent_dim`, `accent_strong`, `accent_fg` | Sparse accent use (links, active, focus, key moments) |
| Semantic | `info`, `success`, `warning`, `danger` (+ dim/tint companions) | Callouts, badges, status |
| Borders / lines | `border_hairline`, `border_subtle`, `border_strong`, `border_focus` | Alpha hairlines, focus indication |
| Code roles | `code_bg`, `code_chrome_bg`, `code_gutter_fg`, `code_button_fg`, `code_button_bg` | Align chrome/Syntax/gutter to theme |
| Spacing | `space_0`..`space_8` (or xs/sm/md/lg/xl) | Cell-based padding/gaps |
| Motion / state | `dur_fast`, `dur_normal`, `dim_overlay`, `hover_overlay`, `disabled_alpha` | Transition timing and state overlays |

Deliverables: expanded `Theme` + helpers (`tone`, `overlay/tint`, semantic
lookups), default theme, gallery token swatches/ramps.

### 0.2 Paint utilities
| Utility | Responsibilities |
|---|---|
| `canvas.py` | `vline`, inner/padded rect, border-safe helpers, bounded drawing |
| `color.py` | `tint(base, overlay, alpha)`, state-overlay helpers, gradient span utilities |
| `measure.py` (if needed) | width/wrap/truncation helpers consistent with Rich measurement |

## Phase 1 — Static atoms (content primitives)

For each primitive: define props contract, implement pure render, add
in-package samples, add gallery section, add snapshot(s). States listed as
“renderable/static” in Phase 1 become interactive in Phase 2.

### 1.1 Text core
| Primitive | Props (contract) | Variants | States/notes |
|---|---|---|---|
| `heading` | `text, theme, level=1..3, anchor_id?` | h1/h2/h3 | h1 bold+space, h2 accent marker, h3 muted/bold |
| `prose` | `content, theme, width?, align?, wrap?, tone?` | body, lead, small, muted | Proper wrapped block (not bare Text), spacing aware |
| `label` | `text, theme, tone?, caps?, spaced?` | default, muted, section/meta | UI labels |
| `emphasis` helpers | `strong/italic/strike/mark(text, theme)` | inline styles | Span/style helpers |
| `truncate` | `text, max_width, ellipsis` | end/middle | Shared text behavior |

### 1.2 Inline & links
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `link` | `text, href?, theme, underline?` | inline, nav | OSC 8 clickable; render states default/hover/focus |
| `inline_code` | `text, theme` | default | Inset chip distinct from prose |
| `badge` | `text, theme, tone, variant` | solid/subtle/outline, status/lang/count | Semantic tones |
| `keycap` | `label, theme, size?` | single, combo | Inline and bar contexts |

### 1.3 Structure
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `rule` | `theme, width?, tone?` | hairline | Baseline divider |
| `divider` | `theme, width?, label?` | plain, labeled | Section break |
| `spacer` | `size, axis?` | vertical/horizontal | Explicit spacing |
| `breadcrumb` | `items[(label, href?)], theme, separator` | compact | Item hover/active styles renderable |
| `section_header` | `title, meta?, theme` | default | Title + spacing/meta row |

### 1.4 Surfaces
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `card` | `title?, body/content, theme, width, padding, fill, border` | borderless, hairline, raised, inset | Correct measure/wrap; hover/focus/selected render hooks |
| `panel` | `content, theme, tone?, padding` | flat, inset | Generic surface |
| `blockquote` | `content, theme, cite?` | default | Left bar/indent, muted treatment |
| `figure` | `content, caption?, theme` | default | Caption styling (placeholder-safe) |

### 1.5 Callouts & feedback (static)
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `callout` | `title, body/content, theme, tone, icon?, compact?` | note/info/tip/success/warning/danger | Accent bar + tinted bg/title by tone |
| `toast` | `message, theme, tone, icon?, action?` | success/info/warn/error | Pill render; show/dismiss timing later |

### 1.6 Code
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `code_panel` | `source, language, filename?, theme, width?, line_numbers?, highlight_lines?, wrap?, copied?` | default, compact | Chrome (dots, filename, lang badge, copy button) pinned/aligned; Syntax themed to tokens; states default/hover/copied/disabled; `.copy()` action contract |

### 1.7 Data & collections
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `table_view` | `headers/columns, rows, theme, align?, compact?, zebra?` | default, compact, borderless | Header band, zebra, overflow/truncation, empty state; row hover/selected hooks |
| `list_block` | `items, theme, ordered?, task?, start?` | ul, ol, task | Composes list items, spacing/indent |
| `list_item` | `content, marker, theme, level, checked?` | bullet, number, task, plain | Marker glyphs themed |
| `key_value` | `items[(k,v)]/label,value, theme` | inline, stacked | Meta/definition rows |
| `empty_state` | `title, body?, icon?, theme` | default | For empty panels/tables/lists |

### 1.8 Navigation atoms & icons (visual only)
| Primitive | Props | Variants | States/notes |
|---|---|---|---|
| `icon` | `name/role, theme, tone?, size?` | role-mapped glyphs | Nerd Font registry + fallbacks |
| `status_dot` | `tone, theme` | filled | Status marker |
| `nav_item` | `label, icon?, theme, active?, indent?, badge?` | rail, tree, inline | Render states default/hover/active/focus |
| `toc_item` | `label, level, theme, active?` | nested levels | Active marker style (glide/spy wiring later) |
| `tag_list` | `tags, theme` | default | Meta chips |

## Phase 2 — Interaction & states

### 2.1 Interaction base
| Module | Contract/responsibility |
|---|---|
| `pointer.py` | Normalize pointer events (pos, button, modifiers, move/down/up/scroll) |
| `hit.py` | Hit regions for painted/custom areas |
| `hover.py` | Hover enter/exit tracking, soft transition hooks |
| `focus.py` | Focus state/ring separate from hover |
| `gestures.py` | Tap, double-tap, long-press, drag, swipe detection |
| `actions.py` | Standard bubbled messages: `Hovered`, `Pressed`, `Tapped`, `LongPressed`, `Focused`, `Copied`, `Dismissed`, etc. |
| `state.py` | Interaction state enum → token/style mapping |
| `scroll_physics.py` | Inertial scroll, rubber-band, smooth anchor glide (scoped/minimal) |

### 2.2 Actionable/stateful atoms
- `button` atom (primary/secondary/ghost/danger): default/hover/focus/pressed/disabled
- `link` interactive behavior (hover/focus/activate) with OSC 8 intact
- `code_panel` copy as real action target + hover reveal + copied flash + disabled/error states
- `keycap`/`keybar` pressed/disabled/context states

### 2.3 Selection & collection interaction
- Row hover/selected for `table_view`, `list_item`, `nav_item`, `toc_item`
- Selectable/focusable `card`
- Consistent focus ring vs hover styling across primitives

### 2.4 Gestures & scroll basics
- Tap/double-tap/long-press unified; right-click == long-press context action
- Scroll container primitive hooks, anchor jump helper, basic inertia hooks

## Phase 3 — Composite bricks (no domain, no shell)

Built only from Phase 1–2 primitives; may hold local UI state, no
docs/downcroc knowledge.
- `hero`, `page_header`, `section`
- `code_group` (tabs/variants wrapper if needed), `callout_group`
- `figure`, meta rows, nav groups
- Composite gallery demonstrating assembly from primitives

## Phase 4 — Explicitly deferred (after primitives are solid)

- markdown-it-py + typed block/content model + block renderer mapping to
  primitives (and prose/inline token-styled rendering)
- 5-zone shell/layout (rail | article | TOC | topbar | keybar), TCSS layout
- TOC scroll-spy wiring, palette/search, overlays/dimming composition
- Real docs/content loading, routing, anchors, `$EDITOR`, copy-link, search
- End-to-end docs app integration and black-box acceptance wiring

## Definition of done (per slice)

- Contract (props/types) defined; render pure from `(props, theme[, state])`
- Variants and applicable states implemented and renderable
- In-package samples/fixtures added (no external paths); gallery section added
- Snapshot/visual tests for key variants and states
- `uv run python scripts/design/shot.py` refreshed; `ruff check/format` clean;
  relevant pytest slice green
- No domain/docs coupling introduced in primitives/paint/interaction

## Open choices (to settle while prototyping)

- Final hex/contrast tuning (iterate via gallery PNG/SVG reviews)
- `prose`/inline richness: custom Text composition vs small internal helper later
- Button/copy affordance visual weight and placement conventions
- Exact boundary where list/blockquote visuals stay primitive vs later mapping concern

# 08 - TUI

Status: deferred for release 1. Release 1 is CLI only; the human interface is described in
`13-interactive-cli.md`. This document stays as the design for a later graphical client.

## What the client is

A Textual application that speaks HTTP and SSE to the daemon. It renders state and sends intent.
It owns no state that matters: kill it, restart it, and the daemon has already moved on.

It is a control room, not a mail app. The common actions are: see what is queued, see what is
being sent, see who replied, fix what broke, adjust a limit.

## Design intent

The terminal is the medium, so the usual crutches are unavailable and a few habits must be
resisted:

- No cards inside panels inside frames. Structure comes from alignment, whitespace, and one
  horizontal rule per band, not from boxes.
- No status pills. A status is a word in a column: `queued`, `sending`, `sent`. Colour is
  secondary, never the only carrier of meaning.
- No dashboard theatre. Gauges exist only where the number is real and actionable: today's
  allowance per account, queue depth, failures.
- No chart that is not read. One sparkline for hourly sends is enough; anything more is
  decoration in a tool meant to be read at a glance.
- Mono is the whole medium here, so hierarchy cannot come from typeface. It comes from case,
  weight, spacing, and placement, and from using exactly one accent colour for focus.

Palette: default terminal foreground, one dimmed tone for secondary text, one accent for the
focused element and the active send indicator, one warning tone for failures and re-auth. No
colour is used to rank data. It survives a 16-colour terminal and a light background.

## Frame

```
 downcroc    daemon 2h14m  unlocked     8 accounts   1 needs re-auth
 ─────────────────────────────────────────────────────────────────────────────
                                                                              
   main screen                                                               
                                                                              
 ─────────────────────────────────────────────────────────────────────────────
 ana@    ██████░░░░  62/200    bo@  ██░░░░░░░░  18/80    cy@  paused
 ─────────────────────────────────────────────────────────────────────────────
 1,204 queued   37 sent this hour   3 failed   41 inbound (37 replies) today
  : commands   ? keys   / filter
```

Four bands, always: identity and daemon state, the screen, the account rail, the numbers.
The account rail is the signature of the app: one line per account showing allowance burn in
place, so the answer to "can I send more today, and from where" is always visible without
navigation. It is real data with a real decision attached, not ornament.

## Screens

| Screen | Key | Purpose |
|---|---|---|
| Overview | `1` | queue depth, live sends, today's numbers, recent replies |
| Batches | `2` | list with sent, failed, inbound, replies |
| Batch | `enter` | per-recipient rows, samples, reply drill-down |
| Accounts | `3` | status, allowance, window, watcher toggle, reconnect |
| Mailbox | `4` | INBOX browse, read-only, per account |
| Threads | `5` | conversations with message and reply counts |
| Failures | `6` | failed jobs, reasons, retry one or all |
| Templates | `7` | list, preview with a sample row, edit in `$EDITOR` |
| Settings | `8` | generated config form, validated on save |
| Logs | `9` | tail with level filter, no credential content by construction |
| Stats | `0` | daily and hourly counts: sent, received, replies, bounces, suppressed, by account and range |

One screen per question. `:` opens a command palette for everything a key does not reach.

Numbers are never computed in the client. The frame band and the overview read
`/api/stats/summary`, `/api/stats/daily` and `/api/stats/hourly`, so what you see matches what the
database recorded even after a restart, and a client that reconnects shows the same figures rather
than a fresh count of whatever it happened to have loaded.

## The approval flow

This is the highest-stakes interaction in the product and gets its own modal.

```
┌ approve batch: october-outreach ──────────────────────────────────────┐
│ 600 recipients   1 sample sent   0 suppressed   0 invalid            │
│                                                                      │
│ rendered sample 3 of 5                    ana@example.com            │
│ ──────────────────────────────────────────────────────────────────── │
│ From: Ana Ruiz <ana@yourdomain.com>                                  │
│ To:   Bo Lind <bo@example.com>                                       │
│ Subj: quick question about Contoso                                    │
│                                                                      │
│   Hi Bo,                                                             │
│   ...                                                                │
│                                                                      │
│ [v] next sample   [s] send this one   [a] approve all   [esc] cancel  │
└──────────────────────────────────────────────────────────────────────┘
```

States:

1. **Reviewing.** Five samples, cycled with `v`. Full rendered headers and body.
2. **Sent one.** `s` sends the visible sample immediately, outside the window and bucket, and
   the footer changes to a single instruction: check the inbox in your mail client, then
   approve the rest.
3. **Approved.** `a` queues the remaining 599. The modal closes and the overview shows the queue
   draining.

`a` is available before `s`, with a one-line confirm, because forcing a test send on someone who
does not want one is its own kind of rudeness. The modal always shows the counts, including
suppressed and invalid, so approving is never approving an unknown.

The dry-run sample's real recipient address is shown. Sending mail to a stranger to test is not
something the UI should make easy to do without noticing.

## Accounts

Per account row: address, status word, today's allowance, window, watcher state.

Actions: reconnect (starts a connect attempt and shows the authorization URL with a copy
binding), verify, toggle watcher, edit allowance and window inline, disable, remove.

A `needs_reauth` account is called out at the top of the screen and in the frame band. The
authorization URL is shown as selectable text with the port already listening, so the flow is
"open this, consent, come back", with the TUI polling the attempt.

## Mailbox

Read-only, per account, INBOX. A thread list, then a message view with headers, text body, and
attachment rows. HTML bodies show the stripped text with a toggle for a sanitized rendering.

`/` filters within the list. Nothing here marks read, moves, deletes, or replies. The footer
says so once, quietly, rather than every time.

## Import

The TUI is not a file picker. Two paths, both explicit:

- `downcroc send path/to/batch.json` parses, submits, and opens the approval modal on success.
- Inside the TUI, `:send` takes a path with tab completion, parsed by the daemon.

Both call the same endpoint. The TUI shows validation results as a table of rows and reasons
before anything is submitted, so a bad file is fixed rather than half-sent.

## Templates

A list, a preview, and an edit action that hands off to `$EDITOR`. On return, the file is
re-read, the preview re-renders against a chosen sample row, and any variable that no longer
resolves is shown in place rather than discovered at send time.

The TUI never holds unsaved template text in memory across a screen change. The file is the
document.

## Settings

Generated from `GET /api/config/schema`, so a new config field appears in the UI without a
client change. Each field carries its type, range, default, and one-line explanation from the
daemon.

Save is `PATCH /api/config`, which validates, writes `config.toml` atomically, reloads, and emits
`config.reloaded`. The form shows the field-level errors the daemon returns. It never writes the
file itself, and it never silently clamps a value you typed.

## Live updates

One SSE subscription for the life of the app, with reconnect and `Last-Event-ID`.

| Event | UI effect |
|---|---|
| `job.sent` | increment counters, move a row |
| `job.failed` | increment the failure count in the frame, flash once, never a modal |
| `message.received` | add to the mailbox list if visible, bump the reply count |
| `reply.matched` | update batch and thread counts |
| `account.needs_reauth` | frame band, banner, account row |
| `config.reloaded` | refresh the settings form and derived labels |
| `config.rejected` | show the field and reason in a quiet banner |
| `gap` | full refetch of the current screen |

Rules: no event triggers a blocking dialog except `needs_reauth`, which is a banner. A tool that
interrupts you every time a send fails is a tool you stop reading.

## Keyboard

`j`/`k` move, `enter` opens, `esc` backs out, `/` filters, `:` commands, `?` keys, `q` quits the
client only (never the daemon), `1`-`0` jump to screens.

Nothing is mouse-only. Every action has a binding and a mention in `?`.

## Empty and error states

Written deliberately, because this is where tools feel unfinished:

| State | Screen shows |
|---|---|
| No accounts | what to add, and the exact command or key to add it |
| Locked vault | an unlock prompt inline, with the reason the rest is unavailable |
| No batches | "no batches yet", the two input formats, and a copyable example path |
| No replies yet | the batch's age and its reply window, not a sad face |
| Daemon unreachable | which path was probed, and a retry |
| Version mismatch | both versions and the refusal, no silent behaviour |

## Design law check

The build must pass this before it is called done, and it is a real pass, not a formality:

- Content is visible by default. No screen starts blank awaiting an animation or an event.
- Nothing is clipped: table columns truncate with an ellipsis at a computed width, headers never
  collide with values, and a long address never pushes a count off the row.
- No decorative motion. A row appearing because an event arrived is real. A spinner that spins
  while nothing is happening is not shipped.
- Colour never carries meaning alone; status words are always present.
- Values are aligned. Numbers right-aligned in a column, addresses left-aligned, statuses at a
  fixed column so the eye can scan vertically.
- Parallel columns line up: in the batch table, sent, failed, inbound, and replies sit on the
  same baselines for every row, whatever the digit count.
- No hairline boxes used as decoration. One rule per band, rounded nowhere.
- Every control works. A binding shown in `?` does something; a footer hint is not a lie.

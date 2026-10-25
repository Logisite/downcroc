# 07 - Inbound and replies

## Scope

INBOX only. No spam folder, no archive, no other folders, no flagging. This is a deliberate
limit and it has a known cost: a reply that the provider files as spam is never seen, so it is
never counted and suppression never learns about it. That cost is stated in the UI, not hidden.

## Watchers

One watcher per account, not per mailbox: an account has exactly one INBOX watcher.

```
unlock
  |
  +-- for each account with watcher_enabled and status == connected:
  |      start a thread: connect, resolve cursor, sync, then IDLE loop
  |
lock or stop
  |
  +-- signal each thread, close connection, join with timeout, abandon if needed
```

Lifecycle rules:

| Event | Effect |
|---|---|
| Unlock | start watchers for enabled accounts |
| Account connected via a connect attempt | start its watcher |
| Account to `needs_reauth` | stop its watcher, no retries |
| Watcher toggle off | stop that watcher, keep its cursor |
| Lock | stop all watchers; the cursor is already durable |
| Batch submit | nothing. Watchers are independent of sending |
| Watcher failure | backoff 5s, 15s, 60s, 5m, 15m, then steady 15m until an event or a manual refresh |

Each watcher is a dedicated thread, because `imap-tools` is synchronous and IDLE is a blocking
call. The thread owns one connection for its lifetime and communicates results to the event loop
through a thread-safe queue. It never touches SQLite.

## The sync loop

```
connect (imap-tools, XOAUTH2 or app password)
  |
  +-- SELECT INBOX, read UIDVALIDITY and UIDNEXT
  |
  +-- if stored UIDVALIDITY differs:
  |      reset cursor to 0, mark the account for a full re-scan
  |      duplicates are handled by Message-ID, so a re-scan is safe
  |
  +-- UID SEARCH UID {last_uid+1}:*
  |      for each message: fetch headers and body, hand to the loop
  |      update last_uid after each successful handoff, in order
  |
  +-- IDLE with a 25 minute timeout
         on "exists": return to SELECT INBOX, refresh UIDVALIDITY/UIDNEXT, then search
         on timeout: return to SELECT INBOX, then reopen IDLE
         on connection error: reconnect with backoff
```

Every IDLE return, including a timeout, goes back through `SELECT INBOX`. That is how a
UIDVALIDITY change is seen even when the server did not announce a new message.

Details that prevent real bugs:

- **`last_uid` advances only after the message is durably stored.** A crash mid-fetch replays
  one message, which the unique index on `(account_id, folder, uidvalidity, uid)` rejects.
  Replay is safe; skipping is not.
- **UIDVALIDITY is stored per account.** Ignoring it is how a mailbox silently stops syncing
  after the server renumbers. A change resets the cursor and forces a full INBOX re-scan.
- **Re-scans are idempotent at the message level.** The unique index on
  `(account_id, message_id)` drops a message seen before the renumber; a missing Message-ID
  falls back to the UID key.
- **The watcher opens INBOX with EXAMINE**, so a sync never sets `\Seen` or any other flag.
- **Search is `UID n:*`, then filtered client-side by uid > last_uid**, because some servers
  return the highest UID for an empty range.
- **IDLE uses a timeout shorter than the server's limit**, so a silently dead connection is
  detected by the client rather than by a missing reply.
- **The first sync on a new account** fetches the last `initial_sync_days` (default 7) of INBOX,
  bounded by a message cap, so connecting a mailbox with 40,000 messages does not stall the
  daemon. Configurable, and skippable.
- **Bodies over a configured size** (default 2 MB) are stored truncated with a flag, and the
  attachment list still records what was there. Full bodies can be fetched on demand.

## Storage

| Piece | Destination |
|---|---|
| Headers and flags | `messages` row |
| Plain text body | `messages.body_text` |
| HTML body | `messages.body_html`, stored as received; sanitized only when rendered |
| Attachments, including inline images | content store, `attachments/<acct>/<msg>/<n>-<name>` |
| Raw message | not stored by default, configurable |

HTML is sanitized when rendered, never when stored, because the stored copy is evidence. The TUI
renders plain text by default and offers a stripped rendering of the HTML.

No binary payload ever touches the database. Images referenced from an HTML body by `cid:` are
extracted like any other part, written to the content store, and indexed with their `Content-ID`
so a rendering can resolve them. The row holds the metadata; the bytes live on disk.

Attachment filenames are sanitized for the filesystem and stored with their original name in the
row, so a download gets the right name without trusting the filesystem.

## DSN and bounces

A bounce is never a reply. Misclassifying one corrupts the reply count, which is the number the
whole product exists to produce.

Detection, any of:

| Signal | Meaning |
|---|---|
| `Content-Type: multipart/report; report-type=delivery-status` | standard DSN |
| Null return path (`Return-Path: <>`) | automated message |
| `From` is `mailer-daemon` or `postmaster` with a `multipart/report` part | common variant |

Classification:

1. Store the message with `is_dsn = 1`.
2. Parse the `message/delivery-status` part: `Final-Recipient`, `Action`, `Status`.
3. Match `Original-Message-ID` when present, otherwise match the recipient address inside the
   report. This resolves to a job.
4. Record the outcome on the message and expose it through batch statistics as a bounce.

A DSN does not change the job's state from `sent`. It was sent; the remote server rejected it.
Overwriting `sent` with `failed` would lose that distinction and would trigger a retry that can
only fail again.

Some DSNs are asynchronous and arrive days later. Some providers send a non-standard
human-readable bounce from a `no-reply` address. Those are stored as ordinary messages and will
appear as inbound without being attributed. The TUI shows unattributed inbound in a separate
list rather than guessing.

## Threading

Run once per ingested message, in this order, stopping at the first hit:

| Step | Match | Result |
|---|---|---|
| 1 | `In-Reply-To` is a known message | link to that message's thread |
| 2 | any id in `References`, newest first, is a known message | link to that message's thread |
| 3 | normalized subject matches a known thread, same correspondent, inside the window | `probable` |
| 4 | no match | create a new thread, unattached to any batch |

Subject normalization: strip repeating `Re:`, `RE:`, `Fwd:`, `FW:`, `AW:`, `SV:`, and leading
whitespace, then lowercase and collapse spaces. A `[tag]` prefix is preserved, because it is
often meaningful.

Why links are stored rather than computed: reply counts are read on every screen, and walking
`References` each time is a graph traversal per row. The walk happens once and the answer is a
row in `thread_links`.

Orphan threads are normal. Cold outreach gets replies that were forwarded, or that arrive from a
new address. They are stored, shown, and not counted.

Every ingested message increments `received` for its hour and day. A confirmed attribution
increments `replies` in the same transaction, on the hourly row, the daily row, and the batch
counters, so the three can never disagree.

## Attribution and counting

A message is **confirmed** when header-based resolution lands it in a thread whose root
`Message-ID` belongs to one of our jobs. It is **probable** when only subject matching landed it
there. Probable messages are stored and shown but are excluded from the headline number.

The headline, per batch:

```
41 inbound (37 replies)
```

| Number | Meaning |
|---|---|
| inbound | every message stored in every thread linked to this batch, including probable, forwards, and bounces |
| replies | messages confirmed by headers, excluding DSNs, excluding probable |

Why this shape: it is a catch-all with a precision statement attached. If the gap is small, the
threads are clean. If the gap is large, something is happening that deserves a look, usually
forwards or a shared mailbox. Showing only the confirmed number would hide real inbound mail;
showing only the total would overstate replies.

Drill-down, batch -> recipient -> thread -> messages, each level a stored aggregate and a query,
not a recomputation.

Batches also report: `sent`, `failed`, `bounces`, `reply rate`, `inbound`, `replies`. Reply rate
is `replies / sent` with a zero guard.

Implementation note for ticket 09: `replies` counts every confirmed, non-DSN message, and
`late_replies` is the subset outside the window. The in-window headline is `replies -
late_replies`. Counts are derived from message rows joined to batch threads until ticket 11 adds
the stored aggregates. The suppression preview returns the address, account, and reason.

## Reply window

`reply_window_days` is per batch, default 60.

It does not stop attribution. A reply on day 200 still attaches to its thread, because discarding
it would be wrong and confusing.

What the window does:

- marks messages inside it as `in_window` and outside as `late` for statistics
- the headline counts in-window replies by default, with late replies shown as a separate
  figure on the batch detail
- suppression always honours late replies, because a person who replied has replied

The window exists so that a year-old batch does not appear to still be growing forever in the
dashboard, not to discard anything.

## Suppression source of truth

The suppression list is not a separate table. It is a query:

> confirmed replies, grouped by account and sender address, whose thread is rooted in a job on
> that account.

This means it cannot drift. Unsubscribing, blocking, and manual suppression lists are out of
scope, so there is nothing to merge or reconcile. If a person replies twice, they are still one
entry. If they reply from a second address, that second address is a different person as far as
the system knows, and this is documented rather than guessed at with fuzzy matching.

## What inbound does not do

| Not done | Consequence |
|---|---|
| Spam folder | missed replies, disclosed |
| Auto-reply detection | an out-of-office counts as inbound and as a confirmed reply, which is usually what you want for suppression but inflates the reply rate. A `Auto-Submitted` or `X-Autoreply` header marks the message so the UI can filter it |
| Content analysis | no sentiment, no classification, no model |
| Marking read | the watcher never sets `\Seen`. Your inbox state is yours |
| Deleting or moving | never. downcroc reads |
| Flagging | never, by design |

The read-only posture on the remote mailbox is worth the small effort it takes: nothing
downcroc does can damage a mailbox it is watching, and that makes it safe to point at a primary
account.

---
title: Backfill log events
commands: []
flags: []
concepts: []
screens: []
---

# Backfill log events

These events come from the Gmail thread id backfill worker (`core/outbound/backfill/*`). It fills missing thread ids on older Gmail messages so they can be grouped into threads correctly. A pass starts with an IMAP Sent-folder sweep on accounts with enough holes, then falls back to per-hole API searches. All ten events are `info` unless noted.

## Worker lifecycle

- `backfill.idle_check` (**info**) — no account has work, so the worker waits for the next recheck interval.
  - `holes`: total holes still recorded across all accounts.

- `backfill.started` (**info**) — a pass began.
  - `holes`: total holes at the start of the pass.
  - `accounts`: number of eligible accounts (lanes) drained in this pass.

- `backfill.account_started` (**info**) — one account's lane started draining.
  - `account`: account id.
  - `holes`: holes queued for this account in this pass.

- `backfill.pass_done` (**info**) — one drain turn finished; the worker either repeats or ends the pass.
  - `resolved`: holes filled in this turn.
  - `missing`: holes finally marked missing in this turn.
  - `left`: holes still recorded after this turn.

- `backfill.finished` (**info**) — the pass ended, either because no holes remain or because it stalled.
  - `resolved`, `missing`, `left`: same meaning as `backfill.pass_done`.

## Lookups

- `backfill.imap_swept` (**info**) — a readonly IMAP Sent-folder sweep finished for one account.
  - `account`: account id.
  - `messages`: messages examined.
  - `hits`: thread ids found by the sweep.
  - `duration_ms`: sweep duration.

- `backfill.resolved` (**info**) — a hole was filled. The write is read-before-write: a hole filled concurrently is not clobbered.
  - `attempt`: send attempt id for the hole.
  - `job`: job id.
  - `account`: account id.
  - `medium`: lookup source, `api` or `imap`.
  - `thread`: thread id written.

- `backfill.ambiguous` (**info**) — an IMAP sweep or API search returned more than one candidate thread id; the hole is not filled from an ambiguous result.
  - `attempt`: send attempt id for the hole.

- `backfill.missing` (**info**) — a hole reached its final strike and is marked missing.
  - `attempt`: send attempt id for the hole.
  - `account`: account id.
  - `strikes`: strike count that triggered the mark (currently `2`).

## Delays and errors

- `backfill.backoff` (**info** or **error**) — a lookup, lane, or pass is waiting before retrying, or a shutdown abandoned a slow pass. An authentication failure or exhausted retries records an error level.
  - `account`: account id, or empty for a worker-level pass delay.
  - `delay_s`: wait in seconds; `0` means no wait (skipped lookup).
  - `cause`: failure code or error class, `shutdown_join`, or `auth`.
  - `detail`: provider error detail, when available.

More: [index.md](index.md), [38-config.md](../../part-iii/38-config.md)

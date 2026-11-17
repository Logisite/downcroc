---
title: Backfill log events
commands: []
flags: []
concepts: []
screens: []
---

# Backfill log events

These events come from the [[backfill]] worker. It fills missing thread ids on older Gmail messages so they can be grouped into threads correctly. The first pass for an account starts with an IMAP Sent-folder sweep when it has enough holes, then falls back to per-hole API searches. The sweep result is cached for the rest of the daemon run, so the Sent folder is scanned once. A drain turn that fills holes continues immediately; the cooldown applies only when a turn fills nothing. A hole is only terminal when the evidence says so: absence is decided after a short settle window with a full-scope search that includes Spam and Trash, and repeated lookup errors mark a hole unresolved instead of missing. The worker wakes from a cooldown as soon as the vault is unlocked, and a connected or reauthing account wakes it too. Use `downcroc backfill status` and `downcroc backfill explain` to see the same state the worker sees. All events are `info` unless noted.

## Worker lifecycle

- `backfill.idle_check` (**info**) — no account has work, so the worker waits for the next recheck interval.
  - `holes`: total holes still recorded across all accounts.
  - `due`, `waiting`, `blocked`, `missing`, `unresolved`: holes split by state.
  - `next_due_at`: when the earliest waiting hole becomes due.

- `backfill.started` (**info**) — a pass began.
  - `holes`: total holes at the start of the pass.
  - `accounts`: number of eligible accounts (lanes) drained in this pass.
  - `due`, `waiting`, `blocked`, `missing`, `unresolved`: holes split by state.

- `backfill.pass_plan` (**info**) — how the pass split the holes between accounts it can drain and accounts it cannot.
  - `due`, `waiting`, `blocked`, `missing`, `unresolved`: holes split by state.
  - `next_due_at`: when the earliest waiting hole becomes due.
  - `blocked_accounts`: `account:reason` entries, for example `acct_...:needs_reauth`.

- `backfill.account_started` (**info**) — one account's lane started draining.
  - `account`: account id.
  - `holes`: open holes (due plus waiting) for this account at the start of this drain turn.
  - `due`, `waiting`: the same split.

- `backfill.pass_done` (**info**) — one drain turn finished; a turn that filled holes repeats immediately, otherwise the worker waits the cooldown or ends the pass.
  - `resolved`: holes filled in this turn.
  - `missing`, `waiting`, `unresolved`, `errors`: other turn outcomes.
  - `due`, `next_waiting`, `blocked`, `left`: holes still recorded after this turn
    (`next_waiting` is the waiting count after the turn, `waiting` the filled-this-turn count).

- `backfill.finished` (**info**) — the pass ended because no due holes remain.
  - `resolved`, `missing`, `waiting`, `unresolved`: cumulative outcomes of the pass.
  - `left`, `blocked`: holes still recorded after the pass.
  - `reason`: why the pass ended, currently `drained`.

- `backfill.cooldown` (**info**) — a drain turn filled nothing, so the worker waits before trying again.
  - `seconds`: configured cooldown (`backfill.pass_cooldown_s`).
  - `left`, `due`: holes still recorded.
  - `reason`: `vault_locked` or `no_progress`.

- `backfill.resumed` (**info**) — a cooldown or idle wait ended early.
  - `reason`: `vault_unlocked`, `account_connected`, or `account_needs_reauth`.

## Lookups

- `backfill.imap_progress` (**info**) — a Sent-folder sweep passed a quarter mark, so a long sweep stays visible.
  - `account`: account id.
  - `messages`: messages examined so far.
  - `total`: messages in the Sent folder.

- `backfill.imap_swept` (**info**) — a readonly IMAP Sent-folder sweep finished for one account. The result is reused for the rest of the daemon run.
  - `account`: account id.
  - `messages`: messages examined.
  - `hits`: thread ids found by the sweep.
  - `duration_ms`: sweep duration.

- `backfill.hole_checked` (**info**, `debug` when resolved) — one API lookup decided, with the evidence it saw. Use it to answer "why was this hole not filled".
  - `attempt`, `job`, `account`: ids for the hole.
  - `message_id`: RFC Message-ID searched for.
  - `decision`: `resolved`, `waiting`, `missing`, `unresolved`, or `skipped`.
  - `reason`: why, for example `absent_settle` or `transient_error`.
  - `sent_results`, `anywhere_results`: search hits in the Sent scope and the full-scope search (which includes Spam and Trash).
  - `provider_result`: the exact message lookup outcome, `hit`, `missing`, `error`, `skipped`, or `not_attempted`.
  - `scope`: which search produced the decision, `sent`, `anywhere`, `provider`, or null when nothing was searched.
  - `age_s`: seconds since the send.
  - `next_check_at`: when the hole is checked again, when scheduled.
  - `duration_ms`: lookup duration.

- `backfill.resolved` (**info**) — a hole was filled. The write is read-before-write: a hole filled concurrently is not clobbered.
  - `attempt`: send attempt id for the hole.
  - `job`: job id.
  - `account`: account id.
  - `medium`: lookup source, `api`, `imap`, or `provider` (exact lookup by the stored Gmail message id).
  - `scope`: which search produced the thread id, `sent`, `anywhere`, `provider`, or `imap`.
  - `thread`: thread id written.
  - `age_s`, `duration_ms`: hole age and lookup duration.

- `backfill.ambiguous` (**info**) — a search returned more than one candidate thread id. The ambiguous result itself is never written; the exact provider-id lookup may still resolve the hole, and without a stored provider id the hole is rescheduled.
  - `attempt`: send attempt id for the hole.
  - `scope`: which search was ambiguous, when known.

- `backfill.retry_scheduled` (**info**) — a hole was not decidable this turn, so it got a next check time instead of a terminal mark.
  - `attempt`, `account`: ids for the hole.
  - `next_check_at`: when the hole is checked again.
  - `delay_s`: seconds from now, when the wait is a backoff.
  - `reason`: `absent_settle` (inside the settle window after the send), `ambiguous`, `provider_error`, or `transient_error`.

- `backfill.missing` (**info**) — a full-scope search found nothing and the settle window after the send has passed, so the hole is marked missing. This is terminal: a `backfill.retry` reopens it.
  - `attempt`: send attempt id for the hole.
  - `account`: account id.
  - `reason`: `absent_after_full_search`.
  - `age_s`: seconds since the send.
  - `strikes`: checks recorded for the hole.
  - `sent_results`, `anywhere_results`, `provider_result`: the evidence of the deciding search.

- `backfill.unresolved` (**info**) — lookups kept failing long enough that the hole can no longer be checked, so it is marked unresolved instead of missing. This is terminal: fix the cause (for example reauthorize the account) and use `backfill.retry`.
  - `attempt`, `account`: ids for the hole.
  - `reason`: `errors_exhausted`.
  - `error`: the last failure code, for example `gmail_api_unavailable`.
  - `age_s`: seconds since the send.

## Delays and errors

- `backfill.backoff` (**info** or **error**) — a lookup, lane, or pass is waiting before retrying, or a shutdown abandoned a slow pass. An authentication failure or exhausted retries records an error level.
  - `account`: account id, or empty for a worker-level pass delay.
  - `delay_s`: wait in seconds; `0` means no wait (skipped lookup).
  - `cause`: failure code or error class, `shutdown_join`, or `auth`.
  - `detail`: provider error detail, when available.

More: [index.md](index.md), [38-config.md](../../part-iii/38-config.md)

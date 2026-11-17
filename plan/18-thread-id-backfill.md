# 18 - Thread id backfill

Status: implemented. This document describes the shipped mechanics of recovering
Gmail provider thread ids for sent mail created before the threading fix
(`63ebc02` introduced `provider_thread_id` capture on send; older attempts have none).
Code wins when this page and the code drift; update this page then.

## Problem

Follow-up sends and inbound attribution resolve a reply's Gmail conversation from
`send_attempts.provider_thread_id`. Attempts sent before the fix carry the outgoing
`Message-ID` but no provider thread id, so follow-ups to that older mail start new Gmail
threads and inbound replies to it fall back to header heuristics. The data needed to fill
the hole is already in the user's Gmail Sent folder; this plan recovers it in the
background with no user action.

## The four media agree on one thread id

One Gmail conversation has exactly one thread id, assigned by Gmail, independent of how a
message was sent or how we observed it. Four paths in downcroc touch that id, two out and
two in, and all four must write the same value in the same encoding.

| # | Direction | Medium | What it reports | Encoding |
|---|-----------|--------|-----------------|----------|
| 1 | out (send) | Gmail REST API `messages.send` with `threadId` in the body | `threadId` in the response | hex string |
| 2 | out (send) | SMTP with `In-Reply-To` / `References` | none at send time; Gmail files the message into a conversation | (recovered later) |
| 3 | in (recover) | Gmail REST API `messages.list`, `q=rfc822msgid:<id>`, `labelIds=SENT` | `threadId` per list result | hex string |
| 4 | in (recover) | IMAP `UID FETCH` on Sent with `X-GM-THRID` | 64-bit integer | integer |

Agreement rules:

1. Medium 1 and 3 return the same hex string for the same conversation; both store it
   verbatim. No conversion.
2. Medium 4 returns the same value as a 64-bit integer. The backfill converts it to the
   canonical hex form (`f"{value:x}"` lower-case, no leading zeros) before writing, so
   values written by every medium are byte-identical.
3. Medium 2 never produces a thread id at send time. The message joins whichever
   conversation Gmail assigns it to (the parent thread when `References` chains correctly,
   a new one otherwise). Media 3 and 4 then report that conversation's id, which is the
   truth we store. Downcroc's SMTP path already sets `In-Reply-To` and `References`, so
   downcroc-originated SMTP sends land in the parent thread.
4. Verification test (part of the black-box suite): send one message through the fake
   provider on the API path, recover it on the IMAP path with the conversion applied,
   assert both stored strings are equal. The fake implements `X-GM-THRID` as the integer
   form of the hex `threadId` it echoes.
5. Standardization consequence: because all four paths converge, follow-up sends resolve
   the parent attempt's `provider_thread_id` without caring which medium produced it, and
   inbound attribution matches on it the same way. `GmailDelivery._resolve_thread_id` and
   the inbound provider-thread attribution treat old recovered ids and new send-captured
   ids identically.

## Recovery strategy: IMAP bulk first, API search fallback

Per account, in this order:

### Stage 1: IMAP bulk sweep (zero API units)

```
connect (XOAUTH2, existing imap-tools setup, own connection, never the watcher's)
  |
  +-- check capability X-GM-EXT-1; if absent -> stage 2 for this account
  +-- resolve the Sent folder with the shared mail/imap primitive
  |      (RFC 6154 special-use discovery; falls back to spec.sent_folder;
  |      Gmail localizes folder names, so the flag is the truth)
  +-- UID FETCH <start>:<end> (X-GM-THRID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])
  |      chunks of 500 uids, 2-5s jitter between chunks, progress logged
  |      at each quarter mark
  +-- build map: message-id header -> int(X-GM-THRID) -> hex
  +-- pull hole pages (page_size) from the repo, look each up, write hits
  +-- leftover holes -> stage 2 list for this account
```

Rules:

- `BODY.PEEK` only. The sweep must never change `\Seen` or any flag.
- Sent messages whose Message-ID header cannot be parsed are skipped silently into the
  leftover list.
- Two Sent messages sharing one Message-ID with different THRIDs: the hole is ambiguous.
  Write nothing, let stage 2 decide.
- IMAP errors: log `backfill.backoff`, skip the sweep for this account this pass,
  and let stage 2 cover every hole from the API. The next pass retries the sweep.
  Rows already written stay written.

### Stage 2: API search fallback (5 units per hole)

Two scopes, in order, one `messages.list` each:

```
messages.list(userId='me', q='rfc822msgid:<message-id>', labelIds=['SENT'])
  -> any hit: decide from the Sent scope, done
messages.list(userId='me', q='rfc822msgid:<message-id>', includeSpamTrash=true)
  -> the full-scope search, spent only when Sent is empty
```

`mail/gmail/read.py::list_messages` carries an optional `label_ids` parameter so the
Sent search is a structured `labelIds` query parameter, not `in:sent` text inside `q`,
and an `include_spam_trash` flag for the full scope. `find_thread_id(message_id)` runs
both scopes and returns a `ThreadSearch` recording which scope decided (`sent`,
`anywhere`, or `none`) and the hit counts of each. `find_sent_thread_id` remains as the
Sent-only wrapper. Classification reads the per-result `threadId`s and the page token.

| outcome | Meaning | Action |
|---|---|---|
| 1 thread id, single page | resolved | write `threadId` verbatim, `scope=sent` or `anywhere` |
| 2+ thread ids | ambiguous | write nothing from the search, log `backfill.ambiguous`, fall through to the provider-id lookup (below) |
| 0 anywhere | absent | settle window, then `missing` (below) |

A message moved out of Sent (for example into Trash) still lives in the mailbox and
still carries its thread id, so the full-scope search recovers it. Only a message
deleted everywhere, or never filed, is genuinely absent.

When both searches return nothing and the attempt already stores
`send_attempts.provider_message_id`, the worker calls
`messages.get(id='<provider id>', format='minimal')` and writes the returned `threadId`.
Gmail can refile an API-sent message under a different RFC
`Message-ID`, so an empty search is not proof the message is gone. The write records
`medium="provider"`, `scope="provider"`. Ambiguous search results still fall through to
this exact lookup.

Cost: 5 units per search (Gmail quota table: list 5, get 20, threads.get 40). The exact
provider-id fallback costs 20 units and runs only after a search finds nothing. A user
with 300 holes costs 1500 units for the searches plus up to 6000 units for exact lookups,
against a 6000 units/min per-user ceiling. The IMAP stage normally resolves everything,
so API units are the exception.

## Startup and lifecycle

```
daemon start (api/app.py lifespan, after services built and bus started)
  |
  +-- count holes: sent attempts, provider_thread_id IS NULL,
  |      message_id IS NOT NULL, joined to accounts with an active Gmail API connection
  |      no transport filter: an SMTP-sent message still sits in the account's Sent
  +-- zero holes -> no worker
  +-- holes -> start worker task, staggered 30s so unlock settles
  |
shutdown: signal, await with timeout, abandon on timeout (rows are per-write safe)
```

Single-flight guard: one worker per daemon. The hourly re-check is the same task sleeping,
not a second task.

## Worker mechanics

```
loop:
  for account in gmail-api accounts, in stable order, max_accounts lanes in parallel:
      drain the account completely:
        pull page_size holes (oldest first)
        stage 1 sweep (once per account per daemon run, cached in memory;
          skipped if the account had fewer than imap_min_holes, default 5,
          -> straight to stage 2; a failed sweep retries on a later pass)
        write every page hole the sweep matched, counting each write as progress
        stage 2 on leftovers
        next page while the last page filled at least one hole; stop when a
          page fills none, so waiting holes cannot block later pages forever
      lane takes the next account
  evaluate pass:
    all holes resolved or marked missing -> idle mode
    a turn filled holes -> next turn immediately, no cooldown
    a turn filled nothing (429s, locked vault, waiting strike) -> cooldown 5m
    two zero-progress turns in a row -> finish the pass and start a new one
  idle mode: re-run the hole count every recheck_s (default 3600);
    new holes -> back to draining; none -> sleep again
```

Concurrency: `max_accounts` lanes in parallel, `max_concurrency` in-flight lookups within
one account (stage 2 calls and IMAP chunk dispatches). Effective in-flight calls are
bounded by `max_accounts * max_concurrency`. Default 1 lane x 2 lookups is effectively
sequential per the original design.

Vault-locked or errored accounts are skipped in lane order and retried next pass; one bad
account never blocks the others.

## Termination and the two terminal marks

"Recursive until all holes are covered" terminates because of two terminal states:

- `missing`: a full-scope search (Sent, then anywhere including Spam and Trash, with the
  provider-id exact lookup) found nothing and `settle_s` (default 900) has passed since
  `started_at`. That covers Gmail search indexing lag; after it, absence is evidence,
  not a guess. The hole never costs API units again and can only return through
  `downcroc backfill retry`.
- `unresolved`: lookups kept failing (transient errors, quota, auth) for longer than
  `retry_after_days` (default 7, the outer cap for repeated errors). "Could not check"
  is a different fact from "not there", so it gets its own status. Fix the cause
  (for example reconnect the account) and retry.

Before the settle window passes, an absent search only schedules a `retry_scheduled`
check. Ambiguous or erroring lookups back off exponentially (`retry_base_s` to
`retry_max_s`). Null progress columns mean due, so holes written before this engine
existed are checked on the first pass after an upgrade.

- The progress state lives in the DB (columns below), not memory, so restarts preserve it.
- The idle re-check counts terminal rows as "no work", so an account with only
  missing/unresolved holes does not wake the worker.

SMTP-sent mail keeps producing holes over time (the send path does not capture a thread
id for SMTP). The idle re-check is what keeps coverage true at any snapshot without a hot
loop. If a later release adds SMTP send-time capture, the loop simply goes quiet.

## Diagnostics

`downcroc backfill status | explain | retry` reads the same state the worker does
(`core/backfill.py::BackfillService`, over `store/repositories/thread_backfill.py`).
`status` splits holes per account into due, waiting, missing, unresolved, and the
block reason (`needs_reauth`, `vault_locked`, `api_not_configured`, ...). `explain`
reports one hole's evidence: scopes tried, hit counts, last result, next check time.
`retry` reopens one terminal hole into the next pass. The same surface exists over HTTP
under `/api/backfill`. The worker also wakes on `account.connected` and
`account.needs_reauth`, so reconnecting an account starts its holes without waiting for
`recheck_s`.

## Schema

New Alembic revision, generated by the CLI against a scratch DB per the project rules.

`send_attempts` gains:

| column | type | meaning |
|--------|------|---------|
| `provider_thread_status` | text, nullable | null = open, `missing` = proven absent, `unresolved` = could not check |
| `thread_missing_at` | text, nullable | ISO timestamp of the terminal mark |
| `thread_first_miss_at` | text, nullable | ISO timestamp of the first inconclusive check |
| `thread_last_checked_at` | text, nullable | ISO timestamp of the last lookup |
| `thread_next_check_at` | text, nullable | ISO timestamp when the hole is due again; null means due |
| `thread_check_count` | integer, default 0 | lookups recorded for the hole |
| `thread_last_result` | text, nullable | last outcome: `resolved`, `absent`, `ambiguous`, `error`, `reopened` |
| `thread_last_scope` | text, nullable | last deciding scope: `sent`, `anywhere`, `provider`, `imap` |
| `thread_last_error` | text, nullable | last failure code, when the check errored |

Plus the `ix_send_attempts_thread_due` index on `(account_id, thread_next_check_at)`.

Hole state lives in `store/repositories/thread_backfill.py` (`ThreadBackfillRepo`:
counts, due pages, resolve, wait, mark missing/unresolved, reopen). Old hole helpers in
`store/repositories/send_attempts.py` moved there; `send_attempts.py` keeps send-path
concerns. The follow-up path keeps reading through
`provider_thread_id_for_job`; the inbound path keeps matching through
`replies.py::_resolve_provider_thread`. Both treat old recovered ids and new
send-captured ids identically without change.

## Configuration

New `[backfill]` section in the runtime config schema, all fields optional:

| field | default | meaning |
|-------|---------|---------|
| `enabled` | true | master switch |
| `page_size` | 50 | holes pulled from the DB per drain turn |
| `max_accounts` | 1 | parallel account lanes |
| `max_concurrency` | 2 | in-flight lookups within one account |
| `jitter_s` | 2.0 | minimum seconds between API/IMAP calls |
| `jitter_max_s` | 5.0 | upper bound of the 2-5s jitter |
| `retry_after_days` | 7 | outer cap for repeated lookup errors before `unresolved` |
| `settle_s` | 900 | seconds after the send before a full-scope miss means `missing` |
| `retry_base_s` | 60 | first delay before retrying an ambiguous or failed lookup |
| `retry_max_s` | 21600 | upper bound of the exponential lookup retry delay |
| `recheck_s` | 3600 | idle-mode hole re-check interval |
| `imap_chunk` | 500 | uids per IMAP FETCH chunk |
| `imap_min_holes` | 5 | below this, skip the IMAP sweep and use stage 2 |
| `startup_delay_s` | 30 | daemon-start stagger before the first hole count |
| `pass_cooldown_s` | 300 | wait after a drain turn that filled no holes |

`startup_delay_s` and `pass_cooldown_s` exist so tests can compress the clock; in
production the defaults hold. The hole count that decides "is there work" counts only
attempts whose job carries an outgoing `Message-ID` (`jobs.message_id`; `send_attempts`
does not store the RFC header itself, so the hole query joins `jobs`).

Rate limiting is by jitter, not by unit accounting: at 2-5s pacing the worker issues
roughly 12-30 calls/min per lane, far inside Gmail's limits. 429/403 on the API path and
IMAP errors still get exponential backoff as a net under the jitter.

## Events

All through `EventLogger`, structured fields, no credentials, no message content:

| event | when | fields |
|-------|------|--------|
| `backfill.started` | worker begins | holes, accounts, due, waiting, blocked, missing, unresolved |
| `backfill.pass_plan` | pass split published | due, waiting, blocked, missing, unresolved, next_due_at, blocked_accounts |
| `backfill.account_started` | each account drain begins | account, holes, due, waiting |
| `backfill.imap_progress` | sweep passes a quarter mark | account, messages, total |
| `backfill.imap_swept` | stage 1 sweep done | account, messages, hits, duration_ms |
| `backfill.hole_checked` | each stage 2 decision | attempt, job, account, message_id, decision, reason, sent_results, anywhere_results, provider_result, scope, age_s, next_check_at, duration_ms |
| `backfill.resolved` | each write | attempt, job, account, medium (`imap`/`api`/`provider`), scope, thread, age_s, duration_ms |
| `backfill.retry_scheduled` | next check time set | attempt, account, next_check_at, delay_s, reason (`absent_settle`/`ambiguous`/`provider_error`/`transient_error`) |
| `backfill.missing` | absent after settle, full scope searched | attempt, account, reason, age_s, strikes, sent_results, anywhere_results, provider_result |
| `backfill.unresolved` | error window exhausted | attempt, account, reason, error, age_s |
| `backfill.ambiguous` | 2+ hits | attempt, scope |
| `backfill.backoff` | API/IMAP error or skipped account | account, delay_s, cause, detail |
| `backfill.pass_done` | drain turn end | resolved, missing, waiting, unresolved, errors, due, next_waiting, blocked, left |
| `backfill.cooldown` | zero-progress turn before waiting | seconds, left, due, reason |
| `backfill.resumed` | wake ended a wait early | reason (`vault_unlocked`/`account_connected`/`account_needs_reauth`) |
| `backfill.finished` | pass drained | resolved, missing, waiting, unresolved, left, blocked, reason |
| `backfill.idle_check` | each re-check | holes, due, waiting, blocked, missing, unresolved, next_due_at |

## Robustness and crash proofing

- Per-row writes only. A crash mid-pass leaves holes; the next startup re-runs the count
  and resumes. No cross-attempt transactions to unwind.
- The worker never touches the watcher's IMAP connection; it opens and closes its own.
- The IMAP sweep is read-only (`BODY.PEEK`, no STORE), so a failure cannot mutate user
  mail state.
- Re-read-before-write race guard: the worker re-reads the attempt row immediately before
  writing, so a follow-up send that naturally resolved the id in the meantime is not
  clobbered.
- Strike state is durable (schema above), so a daemon restart does not restart the
  retry clock or re-spend units on proven misses.
- Idle mode is a sleeping task, not a spawned one, so shutdown has one thing to stop.
- Locked vault: the worker checks credential availability per account per turn; locked
  accounts are skipped, not failed.
- Worst-case stall protection: a pass that makes zero progress twice in a row logs
  `backfill.finished` with `left` counts and enters idle mode anyway, so a permanently
  broken account cannot keep the worker spinning.

## Modules touched

| file | change |
|------|--------|
| `core/outbound/backfill/worker.py` | worker: lifecycle, lanes, due-only drain loop, pass/idle logic, wake events |
| `core/outbound/backfill/lanes.py` | `PassStats` and the per-account `Lane` |
| `core/outbound/backfill/consume.py` | one page turn: sweep hits first, then stage-2 lookups |
| `core/outbound/backfill/imap_stage.py` | stage 1 consumption: sweep map, hit/ambiguous classification |
| `core/outbound/backfill/api_stage.py` | stage 2 settle ladder: resolve, wait, `missing`/`unresolved` marks |
| `core/outbound/backfill/lookups.py` | the Gmail API calls with backoff (search, provider fallback) |
| `core/outbound/backfill/evidence.py` | `Outcome`, `Turn`, age/duration/deadline/backoff helpers |
| `core/outbound/backfill/plan.py` | pass planning: due/waiting/blocked per account with the block reason |
| `core/backfill.py` | `BackfillService` behind the diagnostics command and API |
| `mail/gmail/read.py` | `label_ids` + `include_spam_trash` on `list_messages`; `find_thread_id`, `ThreadSearch` |
| `mail/imap/sent_scan.py` | IMAP bulk sweep with `X-GM-THRID` and hex conversion (raw `imaplib` via `box.client`; imap_tools does not expose Gmail fetch attributes) |
| `mail/imap/folders.py` | `resolve_sent_folder(box, spec)`: special-use discovery with `spec.sent_folder` fallback |
| `store/repositories/thread_backfill.py` | `ThreadBackfillRepo`: counts, due pages, resolve/wait/mark/reopen |
| `store/db/migrations/versions/...` | Alembic revisions (CLI-generated) |
| `runtime/config/schema.py` | `[backfill]` section |
| `api/routes/backfill.py`, `api/schemas/backfill.py` | `/api/backfill/status`, `/holes/{id}`, `/holes/{id}/retry` |
| `cli/commands/backfill.py`, `cli/parser/other.py` | `downcroc backfill status/explain/retry` |
| `api/app.py` | lifespan wiring: start/stop the worker |
| `tests/harness/gmail.py` | fake: stored sent mail with hex thread ids, `rfc822msgid:` + `labelIds` search, sent deletion, IMAP Sent mirroring via the mail-servers fake |
| `tests/harness/fakes.py` | fake IMAP: `X-GM-EXT-1` capability toggle, per-user Sent mailbox, `X-GM-THRID` + `BODY.PEEK[HEADER.FIELDS]` fetch, `\Sent` special-use flag |
| `tests/test_thread_backfill.py` | black-box acceptance |

The inbound attribution query lives in
`store/repositories/replies.py::_resolve_provider_thread`; the backfill does not change
it. Old recovered ids and new send-captured ids match through the same comparison.

Vertical slice: everything above is one feature; shared primitives (repo methods, IMAP
connection setup, jitter helper) are reused from their layers, not duplicated.

## External references to check during implementation

- Gmail API `users.messages.list`: response carries only `id` and `threadId`
  (developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- Gmail API quota table: `messages.list` 5 units, `messages.get` 20, `threads.get` 40,
  6000 units/min per user (developers.google.com/gmail/api/reference/quota)
- `rfc822msgid:` search operator matching the Message-ID header
  (support.google.com/mail/answer/7190)
- Gmail IMAP extensions: `X-GM-EXT-1`, `X-GM-THRID` / `X-GM-MSGID` fetch attributes
  (developers.google.com/gmail/imap/imap-extensions)
- Existing repo behavior this must not break: `06-send-pipeline.md` (send-time capture),
  `07-inbound-replies.md` (watchers own their IMAP connections; the backfill obeys the
  same "never touch SQLite from IMAP threads" boundary by handing results through the
  repo layer in the worker, which runs its own thread per lane)

## Acceptance (black-box)

`tests/test_thread_backfill.py` starts the real daemon and drives it end to end:

1. Seed the fake with sent attempts lacking `provider_thread_id` (pre-fix state).
2. Start the daemon; assert the worker resolves them and the DB shows hex ids.
3. Send one reply; assert it lands in the recovered thread (fake echoes `threadId`).
4. Delete one fake Sent message; assert absence settles into `missing` after `settle_s`.
5. Duplicate Message-ID fixture; assert ambiguous handling leaves the hole and logs.
6. Kill the daemon mid-pass; restart; assert resume without duplicate writes.
7. Assert the four-media equality test from the table above passes.

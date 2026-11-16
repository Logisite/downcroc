# 18 - Thread id backfill

Status: proposed, build-ready. This document is the implementation plan for recovering
Gmail provider thread ids for sent mail created before the threading fix
(`63ebc02` introduced `provider_thread_id` capture on send; older attempts have none).

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
  +-- SELECT the \Sent special-use folder (no folder-name guessing)
  +-- UID FETCH <start>:<end> (X-GM-THRID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])
  |      chunks of 500 uids, 2-5s jitter between chunks
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
- IMAP errors: retry the chunk with backoff 2s, 5s, 15s, 60s, then skip the account this
  pass. Rows already written stay written.

### Stage 2: API search fallback (5 units per hole)

```
messages.list(userId='me', q='rfc822msgid:<message-id>', labelIds=['SENT'])
```

Per Google's API reference the list response carries only `id` and `threadId`, which is
all we need. Classification:

| resultSize | Meaning | Action |
|---|---|---|
| 1 | resolved | write `threadId` verbatim |
| 0 | not in Sent (deleted, or never filed) | strike 1; second strike after `retry_after_days` -> mark `missing` |
| 2+ | ambiguous | write nothing, log, treat as 0 for strike purposes |

Stage 2 is used for: accounts without `X-GM-EXT-1`, holes the IMAP sweep could not see,
and holes whose IMAP result was ambiguous. It is not used when the IMAP sweep already
resolved the account.

Cost: 5 units per hole (Gmail quota table: list 5, get 20, threads.get 40). A user with
300 holes costs 1500 units once, against a 6000 units/min per-user ceiling. The IMAP stage
normally resolves everything, so API units are the exception.

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
        stage 1 sweep (once per account per pass; skipped if the account had
          fewer than imap_min_holes, default 5, -> straight to stage 2)
        stage 2 on leftovers
        next page until the account's hole list is empty
      lane takes the next account
  evaluate pass:
    all holes resolved or marked missing -> idle mode
    holes remain unmarked (429s, locked vault, skipped account) -> cooldown 5m, new pass
  idle mode: re-run the hole count every recheck_s (default 3600);
    new holes -> back to draining; none -> sleep again
```

Concurrency: `max_accounts` lanes in parallel, `max_concurrency` in-flight lookups within
one account (stage 2 calls and IMAP chunk dispatches). Effective in-flight calls are
bounded by `max_accounts * max_concurrency`. Default 1 lane x 2 lookups is effectively
sequential per the original design.

Vault-locked or errored accounts are skipped in lane order and retried next pass; one bad
account never blocks the others.

## Termination and the missing mark

"Recursive until all holes are covered" terminates because of the `missing` mark:

- An attempt with 0 search hits twice, the second strike at least `retry_after_days`
  (default 7) after the first, is marked `missing` in the DB. It never costs API units
  again. Deleted-from-Sent mail is the common case; unbounded retry would burn the
  user's quota forever.
- The strike state lives in the DB (columns below), not memory, so restarts preserve it.
- The idle re-check still counts `missing` rows as "no work", so an account with only
  misses does not wake the worker.

SMTP-sent mail keeps producing holes over time (the send path does not capture a thread
id for SMTP). The idle re-check is what keeps coverage true at any snapshot without a hot
loop. If a later release adds SMTP send-time capture, the loop simply goes quiet.

## Schema

New Alembic revision, generated by the CLI against a scratch DB per the project rules.

`send_attempts` gains:

| column | type | meaning |
|--------|------|---------|
| `provider_thread_status` | text, nullable | null = never tried, `missing` = proven unfillable |
| `thread_missing_at` | text, nullable | ISO timestamp of the second strike |
| `thread_first_miss_at` | text, nullable | ISO timestamp of the first strike |

No new table. Writes are single-row updates through `store/repositories/send_attempts.py`,
which gains a hole-page query (eligible holes, oldest first, page_size) and the
strike/mark helpers. The existing `provider_thread_id_for_job` and
`job_id_for_provider_thread` reads are reused as-is by the follow-up and inbound paths.

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
| `retry_after_days` | 7 | second-strike window for the `missing` mark |
| `recheck_s` | 3600 | idle-mode hole re-check interval |
| `imap_chunk` | 500 | uids per IMAP FETCH chunk |
| `imap_min_holes` | 5 | below this, skip the IMAP sweep and use stage 2 |

Rate limiting is by jitter, not by unit accounting: at 2-5s pacing the worker issues
roughly 12-30 calls/min per lane, far inside Gmail's limits. 429/403 on the API path and
IMAP errors still get exponential backoff as a net under the jitter.

## Events

All through `EventLogger`, structured fields, no credentials, no message content:

| event | when | fields |
|-------|------|--------|
| `backfill.started` | worker begins | holes, accounts |
| `backfill.account_started` | each account drain begins | account_id, holes |
| `backfill.imap_swept` | stage 1 sweep done | account_id, messages, hits, duration_ms |
| `backfill.resolved` | each write | attempt_id, job_id, medium (`imap`/`api`) |
| `backfill.missing` | mark applied | attempt_id, strikes |
| `backfill.ambiguous` | 2+ hits | attempt_id |
| `backfill.backoff` | 429/403/IMAP error | account_id, delay_s, cause |
| `backfill.pass_done` | pass end | resolved, missing, left |
| `backfill.finished` | entering idle mode | totals |
| `backfill.idle_check` | each hourly re-check | holes |

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
| `core/outbound/backfill.py` (new) | worker: lanes, drain loop, pass/idle logic |
| `mail/gmail/read.py` | `find_sent_thread_id(message_id)` wrapping the API search |
| `mail/imap/sent_scan.py` (new) | IMAP bulk sweep with `X-GM-THRID` and hex conversion |
| `store/repositories/send_attempts.py` | hole-page query, strike/mark helpers |
| `store/db/migrations/versions/...` | new Alembic revision (CLI-generated) |
| `runtime/config/schema.py` | `[backfill]` section |
| `api/app.py` | lifespan wiring: start/stop the worker |
| `tests/harness/gmail.py` | fake: IMAP sweep support with `X-GM-THRID` |
| `tests/test_thread_backfill.py` (new) | black-box acceptance |

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
4. Delete one fake Sent message; assert strike-then-miss behavior across `retry_after_days`.
5. Duplicate Message-ID fixture; assert ambiguous handling leaves the hole and logs.
6. Kill the daemon mid-pass; restart; assert resume without duplicate writes.
7. Assert the four-media equality test from the table above passes.

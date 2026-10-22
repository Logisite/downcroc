# 02 - API contract

## The one rule

The daemon does everything. The API only accepts intent and streams truth.

There is no endpoint that performs business logic inline. `POST /api/batches` does not send
mail; it validates, snapshots, creates jobs, and returns. Sending happens in the dispatcher,
whether or not a client is connected to watch it.

## Versioning

All routes live under `/api/v1`. The daemon defines the API: FastAPI generates the OpenAPI
document from the route definitions and the pydantic schemas, serves it at `/openapi.json`, and
that document is the machine-readable description of what the daemon currently does. This file
is the narrative around it, and it is a living description rather than a freeze. Both move with
the code.

Clients are generated from the document rather than hand-written against this file, so a changed
route becomes a regenerated client instead of a client that quietly stops parsing a response. A
renamed or removed route takes `/api/v2` when the change is big enough that mixing them would
confuse a running client; that is a judgement at the time, not a rule written in advance.

The daemon version is in `/api/health` and `service.json`. A client refuses to attach to a
daemon whose major API version differs from its own.

## Authentication

None. The socket is bound to `127.0.0.1` and there is no token, no cookie, and no session.

This is deliberate and its consequences are spelled out in `04-security.md`. In short: any
local process can call this API while the daemon is unlocked. The vault protects credentials
at rest, not the live socket. When remote access becomes a feature, it ships with a token and
a pairing flow; until then, adding auth would be defending a boundary nobody crosses.

## Endpoint map

### Server

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness, version, pid, uptime, API version |
| GET | `/api/status` | daemon state, vault state, queue counts, watcher states |
| GET | `/openapi.json` | the generated spec |

### Vault

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/vault` | locked or unlocked, when unlocked, per-account credential presence |
| POST | `/api/vault/unlock` | body: master password. Derives key, discards password |
| POST | `/api/vault/lock` | drops the key. Running sends finish or are abandoned per `03` |

`GET /api/vault` returns `state`, `path`, `unlocked_at`, `attempts_left`, `retry_after_s`, and
`accounts` (each with `id` and `credential_present`). Unlock takes `{"password": "..."}` and
returns the same shape; lock takes no body and returns it. Neither echoes the password.
`GET /api/status` carries a `vault` object with the state and attempt fields.

Vault errors: `vault_bad_password` (401), `vault_locked` (423), `vault_throttled` (429),
`vault_corrupt` and `vault_already_unlocked` (409), `vault_unavailable` and
`vault_write_failed` (500).

### Providers

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/providers` | declared providers, with auth kind and network settings |

The provider response never includes `oauth_client_secret`. It reports `oauth_configured` so a
client can tell whether a provider can start an OAuth attempt.

### Accounts

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/accounts` | list, with status and send policy |
| POST | `/api/accounts` | body: provider id, address, label |
| GET | `/api/accounts/{id}` | one account |
| PATCH | `/api/accounts/{id}` | update label, enabled, watcher toggle |
| DELETE | `/api/accounts/{id}` | remove account and its credentials |
| POST | `/api/accounts/{id}/connect` | body: app password. Connect a password account |
| POST | `/api/accounts/{id}/verify` | test the credential against the provider |

An account carries `id`, `provider`, `address`, `label`, `status`, `credential_present`,
`created_at`, `last_verified_at`, `last_error`, and the stored send policy as `quota`. Status is
one of `pending`, `connected`, `needs_reauth`, `disabled`, `unverified`. `last_error` carries the
last stable reason code, such as `invalid_grant` or `imap_auth_failed`, and never carries
credential material.

`POST /api/accounts/{id}/verify` uses the cached access token when it is still valid. Add
`?refresh=true` to force a refresh first, which is how a revoked grant is detected immediately.
An IMAP authentication failure moves the account to `needs_reauth` and returns
`account_needs_reauth` (409). A network failure leaves the status alone and returns
`imap_unreachable` (502).

### Connect attempts

An attempt is an OAuth flow owned by the daemon, not by the client that started it. This is
what lets a connect flow survive a TUI restart, and later lets either client finish it.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/accounts/{id}/attempts` | start. Returns id, authorization URL, expiry |
| GET | `/api/attempts/{id}` | pending, succeeded, failed, cancelled, expired |
| POST | `/api/attempts/{id}/cancel` | abort |

An attempt response carries `id`, `account_id`, `kind`, `state`, `authorization_url`,
`created_at`, `expires_at`, and `error`. The state nonce and PKCE verifier are never returned.
Only one attempt per account may be pending; a second start returns `attempt_pending` (409).
Cancellation returns `attempt_not_pending` (409) once the attempt is terminal.

Connect errors: `oauth_not_configured` and `provider_not_configured` (409),
`provider_auth_mismatch` (422), `attempt_pending` and `attempt_not_pending` (409),
`imap_auth_failed` (401), `imap_unreachable` and `imap_tls_failed` (502),
`account_needs_reauth` (409), `credential_missing` (409), and `vault_locked` (423).

### Batches

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/batches` | submit a file path or JSON body. Validates, snapshots, creates jobs |
| GET | `/api/batches` | list with counts: sent, failed, inbound, replies |
| GET | `/api/batches/{id}` | detail, including samples and per-recipient rows |
| POST | `/api/batches/{id}/approve` | `one` or `all`, per the dry-run flow in `06` |
| POST | `/api/batches/{id}/cancel` | stop queued jobs, keep sent ones |
| GET | `/api/batches/{id}/suppression-preview` | who would be skipped and why |

### Jobs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/jobs` | filter by batch, account, state, date |
| GET | `/api/jobs/{id}` | full record, including the rendered body reference |
| POST | `/api/jobs/{id}/retry` | requeue a failed job |
| POST | `/api/jobs/{id}/reassign` | move a queued job to another account |

### Mail, threads, replies

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/messages` | filter by account, folder, thread, date, reply status |
| GET | `/api/messages/{id}` | headers, body, attachment metadata |
| GET | `/api/messages/{id}/attachments/{attachment}` | download a stored attachment |
| GET | `/api/threads` | list threads with message and reply counts |
| GET | `/api/threads/{id}` | ordered messages in the thread |

### Statistics

Every endpoint takes `from`, `to`, and an optional `account_id`, and reads stored aggregates, never
a scan of the job table.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/stats/summary` | sent, failed, received, replies, bounces, suppressed for a range |
| GET | `/api/stats/hourly` | per hour, per account: sent, failed, received, replies, bounces |
| GET | `/api/stats/daily` | per day, per account, plus `quota_limit` so burn can be charted |
| GET | `/api/stats/batches` | per batch: sent, failed, inbound, replies, late replies, bounces, reply rate |
| GET | `/api/stats/accounts` | per account: volume, replies, remaining allowance today |
| POST | `/api/stats/rebuild` | recompute aggregates from `jobs` and `messages`, optionally since a date |

The hourly and daily endpoints report activity, not limits. The only quota in the system is the
per-account daily allowance, exposed as `remaining_allowance` on `/api/stats/accounts` and in the
account object itself. Nothing in this section can throttle a send.

### Failures

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/failed` | records from `failed.jsonl`, with reasons |
| POST | `/api/failed/retry` | retry one or all |

### Config

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | the effective config, plus the on-disk document |
| PATCH | `/api/config` | validated merge. Daemon writes `config.toml`, reloads, emits event |
| GET | `/api/config/schema` | field descriptions for TUI form generation |

### Backup

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/backups` | create a bundle at a given path |
| GET | `/api/backups` | existing bundles known to the daemon |
| GET | `/api/backups/{id}` | progress and result |
| POST | `/api/restore` | restore from a bundle, then restart |

### Events

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/events` | SSE stream, resumable |

## Core schemas

**Account**

| Field | Type | Notes |
|---|---|---|
| id | string | stable, opaque |
| provider | string | `gmail`, `microsoft`, or a declared generic id |
| address | string | the mailbox address |
| label | string | user-facing name |
| status | enum | `pending`, `connected`, `needs_reauth`, `disabled`, `unverified` |
| credential_present | bool | never the credential itself |
| quota | object | daily allowance, window hours, jitter range, enabled; the account's stored policy snapshot |

**Job**

| Field | Type | Notes |
|---|---|---|
| id | string | |
| batch_id | string | |
| account_id | string | bound at creation |
| recipient | string | |
| state | enum | `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled` |
| attempts | int | |
| next_attempt_at | timestamp | null when not waiting |
| message_id | string | minted by downcroc, the attribution anchor |
| subject | string | rendered |
| body_ref | string | content store reference |
| last_error | object | code, message, retryable |

**Batch**

| Field | Type | Notes |
|---|---|---|
| id | string | |
| name | string | from file or user |
| source_ref | string | snapshot path in the content store |
| source_hash | string | sha256 of the snapshot |
| template_ref | string | null when self-contained |
| account_id | string | null when auto-selected per recipient |
| options | object | suppress_replies, reply_window_days, not_before |
| state | enum | `awaiting_approval`, `sending`, `done`, `cancelled` |
| counts | object | queued, sent, failed, suppressed, invalid, inbound, replies, late_replies, bounces |

**Message**

| Field | Type | Notes |
|---|---|---|
| id | string | |
| account_id | string | |
| folder | string | `INBOX` in the current scope |
| uid | int | IMAP UID, the cursor anchor |
| message_id | string | |
| in_reply_to | string | null |
| references | string[] | |
| subject | string | decoded |
| from | object | address and display name |
| to | string[] | |
| date | timestamp | parsed header date |
| is_dsn | bool | bounce report |
| reply_state | enum | `none`, `confirmed`, `probable` |
| thread_id | string | null until linked |
| job_id | string | null, set when a confirmed reply is attributed |

**Thread**

| Field | Type | Notes |
|---|---|---|
| id | string | |
| root_message_id | string | the outbound Message-ID that started it |
| subject | string | normalized for display |
| batch_id | string | null |
| message_count | int | |
| reply_count | int | confirmed replies only |
| first_seen | timestamp | |
| last_seen | timestamp | |

## Event stream

`GET /api/events` returns `text/event-stream`. Each event carries:

| Field | Meaning |
|---|---|
| `id` | monotonic sequence number |
| `type` | dotted name, listed below |
| `ts` | ISO timestamp |
| `data` | JSON payload, minimal: ids, not full objects |

Event types:

```
daemon.ready          daemon.stopping
vault.unlocked        vault.locked
account.added         account.connected      account.needs_reauth    account.removed
batch.submitted       batch.awaiting_approval  batch.started
batch.completed       batch.cancelled
job.queued            job.started            job.sent
job.retry_wait        job.failed             job.sent_unconfirmed
message.received      reply.matched          bounce.received
quota.consumed        watcher.state_changed  config.changed
stats.pruned          backup.created         backup.failed          restore.pending
```

**Resume semantics.** The daemon keeps a ring buffer of the last 10,000 events in SQLite. A
client that reconnects sends `Last-Event-ID`; the daemon replays from the buffer when it can,
and otherwise tells the client to refetch state with a `gap` event. Events are a notification
mechanism, never the source of truth. A client that missed everything must be able to rebuild
its screen from HTTP alone, and that path is tested.

**Payload rule.** Events carry ids and deltas, not full objects. A client that needs detail
fetches the object. This keeps the stream small and stops two representations of the same
record from drifting.

## Error model

Every non-2xx response is a JSON object:

| Field | Meaning |
|---|---|
| error | stable machine code, such as `vault_locked` or `account_needs_reauth` |
| message | one sentence, safe to display |
| status | HTTP status |
| hint | optional next action, such as "unlock the vault" |

Validation failures include a `fields` map keyed by input path. The TUI renders `message` and
`hint`; it never displays a raw traceback. The daemon logs the traceback with a correlation
id that is also returned, so a user report can be matched to a log line.

## Web client reuse

When the browser client arrives it is served by the same daemon on the same port, at `/`. It
uses the same endpoints, the same SSE stream, and the same error model. The only new code is
static assets, and the only daemon change is one route that serves them.

If a feature cannot be built from this API, the API is wrong. It is never acceptable to add a
second execution path for the browser.

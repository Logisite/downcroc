# 03 - Data model

## Storage split

| What | Where | Why |
|---|---|---|
| Config | `config.toml` | human editable, portable, one source of truth |
| Job and account state | SQLite | transactional, queryable, survives restart |
| Received mail bodies | SQLite | the reply engine queries them constantly |
| Statistics and counters | SQLite | must outlive the pruning of the rows they summarise |
| Batch snapshots | content store | large, write-once, hash verified |
| Templates | `templates/` | diffable, git-friendly, edited by the TUI |
| Attachments | content store | the real size driver, never in the DB |
| Credentials | `vault.enc` | encrypted at rest, never in the DB |

The asymmetry is intentional: mail bodies are queried and joined, batch bodies are read once
when sending. Put each where it is actually used.

## Database

SQLite with SQLAlchemy 2.0 declarative models, WAL mode, `synchronous=NORMAL`, and one writer at a
time. All timestamps are UTC ISO-8601 with milliseconds. All ids are opaque strings, prefixed by
type (`acct_`, `bat_`, `job_`, `msg_`, `thr_`, `att_`, `evt_`).

The tables below are the schema the models describe. Everything uses `text` ids and integer
counters; there is no surrogate integer key anywhere except the event sequence.

### `accounts`

| Field | Type | Notes |
|---|---|---|
| id | text pk | `acct_...` |
| provider_id | text | matches a declared provider |
| address | text | unique per provider |
| label | text | user-facing |
| status | text | `pending` before a credential exists, `connected` after a successful login, `needs_reauth` when a credential is rejected or a grant is revoked, `disabled` when turned off, `unverified` reserved for a stored credential that has not been proven |
| credential_key | text | key inside the vault, never a credential |
| created_at | text | |
| last_verified_at | text | null until first verify |
| daily_allowance | int | successful sends per local day |
| window_start | int | local hour sending opens |
| window_end | int | local hour sending closes |
| jitter_min | int | minimum seconds between sends on this account |
| jitter_max | int | maximum seconds between sends on this account |
| max_in_flight | int | concurrent sends allowed on this account |
| enabled | int | participates in dispatch |

The policy columns are copied from the `[sending]` config section when the account is created.
They live on the row because accounts differ and the account API edits one account at a time.

### `account_state`

| Field | Type | Notes |
|---|---|---|
| account_id | text pk | |
| watcher_enabled | int | toggle from the TUI |
| uidvalidity | int | server UIDVALIDITY for the current cursor |
| last_uid | int | highest UID ingested for that UIDVALIDITY |
| last_sync_at | text | |
| last_error | text | |
| consecutive_failures | int | drives watcher backoff |

### `batches`

| Field | Type | Notes |
|---|---|---|
| id | text pk | |
| kind | text | `campaign` or `follow_up` |
| parent_batch_id | text | null unless `kind` is `follow_up` |
| name | text | |
| source_ref | text | content store path of the snapshot |
| source_hash | text | sha256 of the snapshot |
| source_kind | text | `json` or `csv` |
| schema_version | text | null for CSV, `downcroc.campaign/v1` for JSON |
| campaign_key | text | producer key, null for CSV |
| producer_json | text | producer metadata, stored and never used for sending |
| template_ref | text | null for JSON, required for CSV |
| account_id | text | null unless routing is fixed |
| routing_json | text | mode, include, exclude, and the resolved assignment count |
| approval | text | `review` or `auto` |
| options_json | text | suppress_replies, reply_window_days, not_before, stop_on, allow_duplicates |
| state | text | `awaiting_approval`, `sending`, `done`, `cancelled` |
| created_at | text | |
| approved_at | text | null until approval |

### `jobs`

| Field | Type | Notes |
|---|---|---|
| id | text pk | |
| batch_id | text | |
| account_id | text | bound at creation |
| recipient | text | |
| recipient_name | text | null |
| source_kind | text | `json` or `csv` |
| source_key | text | JSON message key, null for CSV |
| source_index | int | message index or CSV row number |
| step_key | text | follow-up step key, null for an initial message |
| parent_job_id | text | null for an initial message |
| thread_root_job_id | text | the job whose Message-ID anchors the thread |
| vars_json | text | template variables or the source recipient object |
| subject | text | rendered at creation |
| body_ref | text | content store path of the rendered message |
| state | text | see state machine |
| attempts | int | |
| next_attempt_at | text | null when not waiting |
| lease_owner | text | daemon instance id |
| lease_expires_at | text | null when not held |
| message_id | text | minted by downcroc, unique |
| last_error_code | text | null |
| last_error_message | text | null |
| retryable | int | null until first failure |
| created_at | text | |
| updated_at | text | |
| sent_at | text | null |

Indexes: `(batch_id, state)`, `(state, next_attempt_at)`, `(account_id, created_at)`,
`(thread_root_job_id)`, unique `message_id`, unique `(batch_id, source_key)` where
`source_key` is not null, unique `(parent_job_id, step_key)` where `step_key` is not null.

### `messages`

| Field | Type | Notes |
|---|---|---|
| id | text pk | |
| account_id | text | |
| folder | text | `INBOX` in current scope |
| uid | int | unique per account, folder, and UIDVALIDITY |
| uidvalidity | int | server UIDVALIDITY that assigned this UID |
| message_id | text | header, may be null if malformed |
| in_reply_to | text | null |
| references_json | text | array |
| subject | text | decoded |
| from_address | text | |
| from_name | text | |
| to_json | text | array |
| date | text | parsed header date, falls back to ingest time |
| size | int | |
| is_dsn | int | bounce report |
| reply_state | text | `none`, `probable`, `confirmed` |
| thread_id | text | null until linked |
| job_id | text | null until attributed |
| body_text | text | nullable |
| body_html | text | nullable |
| body_truncated | int | a stored body hit the size cap |
| ingested_at | text | |

Indexes: unique `(account_id, folder, uidvalidity, uid)`, unique
`(account_id, message_id)`, `(thread_id, date)`, `(job_id)`, `(message_id)`.
The message-id index makes a UIDVALIDITY re-scan idempotent; the UID index catches
the same message arriving twice in one UIDVALIDITY.

### `attachments`

No binary payload is ever stored in the database. This table is the index into the content store.

| Field | Type | Notes |
|---|---|---|
| id | text pk | `att_...` |
| message_id | text | |
| filename | text | original name, sanitized only in the stored path |
| content_type | text | |
| size | int | |
| path | text | content store path |
| hash | text | sha256 |
| inline | int | 1 when the part is referenced from an HTML body by `cid:` |
| content_id | text | the `Content-ID` value, for inline images |

### `threads`

| Field | Type | Notes |
|---|---|---|
| id | text pk | |
| root_message_id | text | root message id, outbound once attribution succeeds |
| subject | text | normalized |
| batch_id | text | null when not started by a batch |
| message_count | int | denormalized, recomputed on insert |
| reply_count | int | confirmed only |
| first_seen | text | |
| last_seen | text | |

### `thread_links`

| Field | Type | Notes |
|---|---|---|
| message_id | text | internal id |
| thread_id | text | |
| relation | text | `root`, `reply`, `probable` |

Explicit links rather than walking `References` at query time. The walk happens once, on
ingest, and the answer is stored, so reply counts are a cheap aggregate rather than a graph
traversal on every screen.

### `attempts`

| Field | Type | Notes |
|---|---|---|
| id | text pk | |
| account_id | text | |
| kind | text | `oauth` |
| state | text | `pending`, `succeeded`, `failed`, `cancelled`, `expired` |
| authorization_url | text | |
| state_token | text | CSRF nonce for the callback |
| callback_port | int | |
| created_at | text | |
| expires_at | text | |
| error | text | null |

One pending attempt per account is enforced in the service rather than by a partial unique index,
because SQLite partial indexes are awkward through Alembic. The row survives completion. An
attempt is deleted with its account by the foreign key cascade. `state_token` is the callback
nonce and is never returned by the API; `authorization_url` is.

### `quota_buckets`

| Field | Type | Notes |
|---|---|---|
| account_id | text | |
| bucket_start | text | local midnight |
| sent | int | |

Primary key `(account_id, bucket_start)`. Survives restart so restarting is not a way to reset
your own allowance. Daily only: there is no weekly cap in the first build, and a column for one
that is never written would be a lie in the schema.

### `activity_hourly`

| Field | Type | Notes |
|---|---|---|
| account_id | text | |
| hour_start | text | truncated local hour |
| sent | int | jobs that reached the wire and were accepted |
| failed | int | terminal failures |
| received | int | messages ingested, DSNs included |
| replies | int | confirmed replies only |
| bounces | int | DSNs attributed to a job |
| suppressed | int | recipients skipped by suppression |

Primary key `(account_id, hour_start)`, plus an index on `hour_start` so a range across all
accounts is one scan.

### `activity_daily`

| Field | Type | Notes |
|---|---|---|
| account_id | text | |
| day | text | local date, `YYYY-MM-DD` |
| sent | int | |
| failed | int | |
| received | int | |
| replies | int | |
| bounces | int | |
| suppressed | int | |
| quota_limit | int | allowance in force that day, so burn can be charted against it |

Primary key `(account_id, day)`. Maintained live alongside the hourly row, and reconciled by a
midnight rollup that recomputes the day from `activity_hourly` before the day is closed. Kept far
longer than the hourly rows, because daily history is what people actually look at.

### `batch_counters`

| Field | Type | Notes |
|---|---|---|
| batch_id | text pk | |
| queued | int | |
| sent | int | |
| failed | int | |
| suppressed | int | |
| invalid | int | rejected at validation |
| inbound | int | every message in every linked thread |
| replies | int | confirmed |
| late_replies | int | confirmed, outside the batch's reply window |
| bounces | int | |
| updated_at | text | |

Incremented in the same transaction as the event that causes it: a job reaching `sent` bumps
`sent`, an ingested message bumps `inbound` and, when confirmed, `replies`. There is no
background aggregation job whose failure would leave the numbers wrong.

### `events`

| Field | Type | Notes |
|---|---|---|
| seq | integer pk | monotonic |
| type | text | |
| ts | text | |
| payload_json | text | ids and deltas only |

Pruned to the newest 10,000 rows. This is the SSE replay buffer, not an audit log.

### `failed_queue`

| Field | Type | Notes |
|---|---|---|
| job_id | text pk | one row per failed job |
| batch_id | text | |
| account_id | text | |
| recipient | text | |
| code | text | stable reason code |
| message | text | human readable reason |
| retryable | integer | null, true, or false |
| attempts | integer | attempts at the failure boundary |
| failed_at | text | |

Mirrors `failed.jsonl` so the TUI can count and filter without parsing a file. The JSONL file
is the durable, portable record; the table is the query surface. The file is appended first,
then the row is inserted, and startup reconciliation reinserts any row missing from the table
whose job is still `failed`. Retrying rewrites the file without that job, deletes the row, and
returns the job to `queued` with its attempt count reset.

## Statistics and activity

Counts are stored, not computed on read. Two reasons:

1. **Retention.** Jobs are pruned at 30 days and mail at 90. If the numbers were derived from
   those rows at query time, your history would disappear because a cleanup ran.
2. **Queryability.** "How many did I send yesterday, per account, and how many came back" is a
   single indexed lookup against `activity_daily`, not a scan of every job ever created.

Everything in this section is observation. The only quota in the system is the per-account
**daily allowance**, accounted for in `quota_buckets`. The hourly rows exist so you can see the
shape of a day: when the sends went out, where a burst happened, which account was quiet until
the evening. Nothing in the dispatcher enforces a per-hour number, and there is no hourly cap to
raise or lower.

| Question | Source |
|---|---|
| Sent today, per account | `activity_daily` by `(account_id, day)` |
| Sends per hour, any range | `activity_hourly` by `hour_start` |
| Peak hour last week | `max(sent)` over `activity_hourly` |
| Received against replies, by month | `activity_daily`, summed by month |
| How a batch performed | `batch_counters` by primary key |
| Which recipients replied | `jobs` joined to `messages` on `job_id` |
| Remaining allowance right now | `quota_buckets` for today |
| Inbound with no attribution | `messages` where `job_id is null` and `is_dsn = 0` |

The aggregates are derived, and therefore rebuildable. `downcroc stats rebuild [--since DATE]`
walks `jobs` and `messages` and rewrites the hourly, daily, and batch rows. It runs after a
restore, and on demand when someone suspects a number.

The invariant that makes this honest: while raw rows are retained, for any period still covered
by them,

```
sum(activity_hourly.sent) == count(jobs where state in ('sent', 'sent_unconfirmed'))
```

That check runs after every restore and after every rebuild. It does not run on every startup,
because a full comparison on a large installation is not worth the seconds.

Definition of each number, so the UI cannot drift from the schema:

| Number | Counts | Does not count |
|---|---|---|
| sent | jobs accepted by SMTP, including dry-run samples | queued, awaiting approval, cancelled, suppressed |
| failed | terminal failures | retries in progress, jobs waiting to retry, work paused by re-auth |
| received | messages ingested into INBOX | messages skipped by initial sync bounds |
| replies | confirmed replies by headers | probable matches, DSNs, forwards, unattributed inbound |
| bounces | DSNs attributed to a job | unattributed DSNs |
| suppressed | recipients skipped at submit or approval | invalid rows |

## Job state machine

```
                    +-----------+
      created ----> |  queued   | <---------------------+
                    +-----+-----+                       |
                          |                             |
              lease taken |                             |
                          v                             |
                    +-----------+   transient failure   |
                    |  sending  |----------+            |
                    +-----+-----+          |            |
                          |                v            |
        accepted by SMTP  |          +-----------+      |
                          |          | retry_wait|------+  attempt <= 5
                          v          +-----+-----+
                    +-----------+          |
                    |   sent    |          | attempts exhausted or permanent
                    +-----------+          v
                                     +-----------+
                                     |  failed   |
                                     +-----------+
```

| State | Meaning | Exits |
|---|---|---|
| `awaiting_approval` | batch submitted, dry run not yet approved | `queued` on approval, `cancelled` on reject |
| `queued` | ready, waiting for an account window and allowance | `sending` when leased |
| `sending` | a worker holds a lease and is talking to SMTP | `sent`, `retry_wait`, `failed`; a crash leaves the row here for reconciliation |
| `retry_wait` | transient failure, waiting for `next_attempt_at` | `sending`, or `failed` when attempts reach 5 |
| `sent` | SMTP accepted and the result was recorded | terminal |
| `sent_unconfirmed` | reserved in the enum | not used by the current send path |
| `failed` | permanent, or attempts exhausted | `queued` on manual retry only |
| `cancelled` | batch cancelled | terminal |

**Crash reconciliation is not optional.** SMTP has no idempotency key. The job moves to
`sending` before the wire and is only marked `sent` after the server accepts. If the process
dies in between, the row stays `sending`. On the next unlock, the daemon searches the Sent
folder for the minted `Message-ID`: found means `sent`; not found means the message never left,
so the row returns to `queued` and is sent again. Sending blindly without that search would
duplicate mail to a real person, which is the worst failure this system can produce.

## Content store

```
content/
  batches/<bat_id>/source.json      # immutable snapshot taken at submit
  jobs/<job_id>/message.eml         # rendered message; identity and Date headers rewritten at send
  attachments/<acct>/<msg_id>/<n>-<name>
  recovery/<job_id>.json            # payload able to reconstruct a failed job
```

Rules:

- Snapshots are write-once. Editing or deleting the original file after submit changes
  nothing.
- Every reference stored in SQLite carries a hash. A read verifies the hash and reports
  corruption rather than rendering something unexpected.
- Paths are relative to the data directory and validated on read: no absolute paths, no
  `..`, no symlink following.
- Deleting a content file never deletes the metadata row. The row records that the content is
  missing, and the TUI shows it as such instead of erroring.

## Migrations

The schema is defined with SQLAlchemy declarative models and versioned with Alembic. There is no
hand-written SQL migration and no hand-mapped row code.

```
alembic.ini
migrations/
  env.py
  versions/2026_10_22_0001_initial.py
```

Rules:

- `uv run alembic revision --autogenerate -m "add attempts"` generates a migration from the
  models. It is never committed unread: the generated operations are reviewed, corrected when
  they are wrong, then applied.
- `uv run alembic upgrade head` runs on every daemon start, before anything reads a table.
- SQLite cannot `ALTER` most things. `env.py` sets `render_as_batch=True`, so generated migrations
  use table rebuilds where they must.
- One linear history, no branches. A migration that has run anywhere is never edited; a mistake is
  corrected by the next one.
- No downgrade path in code. Restoring an older bundle runs migrations forward.
- `alembic_version` is the only version record. A second version table would be a copy of the same
  truth.

A database whose revision is not in the local Alembic history refuses to open, because it was
written by a newer build. That is the same rule the backup bundle follows in `09-backup-restore.md`.

Backups carry the app version and the Alembic revision. See `09-backup-restore.md`.

## Retention

| Thing | Default | Configurable | Notes |
|---|---|---|---|
| Jobs | 30 days or 10,000 rows | yes | oldest completed first; pending never pruned |
| Mail bodies and messages | 90 days | yes, per account | attachments pruned with their message |
| Hourly activity | 90 days | yes | rolled into daily at local midnight before pruning |
| Daily activity | 730 days | yes | the long memory, survives job and mail pruning |
| Batch counters | as long as the batch | yes | the batch row outlives its jobs |
| Events | 10,000 rows | yes | ring buffer |
| Logs | 10 MB x 5 files | yes | rotation on size |
| `failed.jsonl` | never pruned | no | the user decides when to clear |
| Batches | kept while any job exists | yes | snapshot retained for provenance |

Pruning runs on a timer, and every prune emits a `stats.pruned` event with counts so the
effect is visible rather than mysterious.

## Durability

Everything behaviour-affecting is persisted. Specifically:

| State | Why it must survive |
|---|---|
| Job rows and states | no lost or duplicated work |
| Leases and expiry | a killed daemon must not strand a job in `sending` |
| Quota counters | restarting must not reset the allowance |
| Aggregate counters | the numbers must outlive the rows they were computed from |
| Watcher UID cursors | no replay, no gap |
| Event sequence | resumable streams and gap detection |
| Account status and `needs_reauth` | no silent auth death |
| Batch snapshots and hashes | provable content of what was sent |

Startup order is fixed: open the database, run migrations, reconcile leases and `sending` rows
against the Sent folder, reconcile `failed.jsonl` against `failed_queue`, rebuild quota counters
from `quota_buckets` if the cache is cold, then start watchers, then start the dispatcher,
then bind the API. Anything that can lie about state is settled before anything reads it.

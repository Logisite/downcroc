# 09 - Job portability, reassignment, and deletion lifecycle

**What to build:** make queued work movable, convertible, and removable. Today `jobs.account_id` is `ondelete="RESTRICT"` and no job delete exists, so one job pins an account forever and the `account_in_use` hint points at a command that does not exist. Add, as one coherent feature set: job cancel and delete, batch delete, failure purge, template and backup deletion, account deletion preview, explicit `--reassign-to` on account deletion, live batch and job reassignment, account archive, a portable job export/import bundle that works independently of deletion, and a vanilla conversion that turns an extracted batch into a plain `downcroc.campaign/v1` campaign any other downcroc install can submit with no shared state. The bundle must be batch aware and selectable: all jobs for an account, one batch, named jobs, a state, or a created or sent date window, so a week long campaign that was paced across days can be lifted out of a banned account and pointed at a live one. Any conversion that would make already contacted recipients sendable again must stop and require the user to type `yes`, because a vanilla campaign carries no per recipient state and will duplicate every message it already sent. Because these operations are destructive, ship a `downcroc help jobs` topic and a `guides/job-portability.md` page in the packaged book, both offline. The daemon owns every rule, every state change, and every API. The CLI is only a client.

**Blocked by:** 03 - Authenticated daemon API and CLI, and 04 - Unified product documentation and terminal access for the book page.

**Status:** ready-for-agent

## Ownership rule

Daemon:

- All selection, validation, state transitions, content store reads and writes, counter rebuilds, audit events, and confirmation checks live in `core/` services behind `/api`.
- Export assembles and streams the bundle. Import parses, verifies, writes, and rolls back.
- Nothing in the CLI opens SQLite, reads the content store, or decides whether a job may move.

CLI:

- Flags in, HTTP out, render the response. `--dry-run` maps to a daemon dry run. `--yes` maps to the API confirmation field. The interactive prompt is a CLI affordance that then sends the same confirmed call.
- Every CLI command in this ticket must have a matching endpoint, so a script can do it without the CLI.
- No CLI side filtering that the API cannot reproduce.

## Schema facts that shape the design

- `jobs.account_id` FK is `ondelete="RESTRICT"`. One job pins an account forever.
- `jobs.batch_id` is NOT NULL. Every job belongs to a batch, including manual jobs.
- `jobs.message_id` is UNIQUE. An import cannot reuse the old one.
- `jobs.body_ref` points into the content store, so a bundle must carry bodies.
- `parent_job_id` and `thread_root_job_id` are self references and need remapping.
- Job states: `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.
- Batch states: `awaiting_approval`, `sending`, `done`, `cancelled`.
- `messages.job_id` links inbound mail to a job. Mail does not travel with a job.
- Suppression is derived from inbound messages per account. It does not travel.
- `quota_buckets` is per account per day. Imported volume spends the target allowance.
- `batch_counters` is a denormalized cache and must be rebuilt for every touched batch.
- `failed_queue.job_id` cascades from `jobs`.
- There is no `scheduled_for` column. A week long campaign is paced by `sending.daily_allowance` (200 per account per day by default), the send window, and jitter. Date filters therefore apply to `created_at` and `sent_at`, not to a per job schedule.

## API contract

Every destructive call requires `confirm=true` (query) or `{"confirm": true}` (body) and returns `confirmation_required` without it, so scripts cannot skip the gate by avoiding the CLI.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/jobs/{job_id}/cancel` | Cancel one job |
| DELETE | `/api/jobs/{job_id}?confirm=true` | Delete one terminal job |
| GET | `/api/jobs/deletion?account_id=&state=` | Deletion preview, no writes |
| POST | `/api/jobs/reassign` | Move jobs between accounts |
| GET | `/api/jobs/export?...` | Stream a zip bundle |
| POST | `/api/jobs/import?account_id=` | Import a zip bundle |
| GET | `/api/batches/{batch_id}/export?...` | Stream a batch bundle, vanilla or native |
| GET | `/api/jobs/schema` | JSON Schema for the bundle manifest |
| GET | `/api/accounts/{account_id}/deletion` | Counts and blockers |
| DELETE | `/api/accounts/{account_id}?confirm=true` | Delete with `reassign_to` or `force_jobs` |
| POST | `/api/accounts/{account_id}/archive?confirm=true` | Archive, keep history |
| POST | `/api/accounts/{account_id}/unarchive?confirm=true` | Restore |
| POST | `/api/batches/{batch_id}/reassign` | Move a whole batch |
| DELETE | `/api/batches/{batch_id}?confirm=true` | Delete a terminal batch |
| DELETE | `/api/failures/{job_id}?confirm=true` | Forget one failure |
| POST | `/api/failures/purge?confirm=true` | Purge failures by state or age |
| DELETE | `/api/templates/{name}?confirm=true` | Delete a template |
| DELETE | `/api/backups/{name}?confirm=true` | Delete a backup |
| POST | `/api/backups/prune?keep=N&confirm=true` | Keep the newest N |
| GET | `/api/doctor/integrity` | Orphans, missing bodies, counter drift |

Reassign request:

```json
{
  "from_account_id": "acct_old",
  "to_account_id": "acct_new",
  "job_ids": ["job_a"],
  "batch_ids": ["bat_q4"],
  "states": ["queued", "awaiting_approval", "retry_wait"],
  "created_since": "2026-10-20T00:00:00Z",
  "created_until": "2026-10-27T00:00:00Z",
  "include_failed": false,
  "force": false,
  "dry_run": true
}
```

Reassign response: `{jobs, batches, skipped: [{id, reason}], dry_run}`.

Export endpoints accept `vanilla=true` and `acknowledge_duplicates=true`. Import accepts `requeue_sent=true` and `acknowledge_duplicates=true`. Any request that would make already sent recipients sendable again is refused with `duplicate_ack_required` and a body carrying `sent`, `total`, and `recipients` (first 10), so the CLI prompt is a rendering of a daemon decision and cannot be skipped by calling the API directly.

## CLI surface

| Command | Endpoint |
|---|---|
| `downcroc job cancel ID` | `POST /api/jobs/{id}/cancel` |
| `downcroc job delete ID [--force] [--dry-run] [--yes]` | `DELETE /api/jobs/{id}` |
| `downcroc job reassign --account OLD --to NEW [--job ID ...] [--batch ID ...] [--state ...] [--since] [--until] [--include-failed] [--dry-run] [--yes]` | `POST /api/jobs/reassign` |
| `downcroc job export [--account ID] [--batch ID ...] [--job ID ...] [--state ...] [--since] [--until] [--sent-since] [--sent-until] [--include-sent] [--include-batches] [--vanilla] [--acknowledge-duplicates] -o PATH [--force]` | `GET /api/jobs/export` |
| `downcroc batch export ID [--vanilla] [--include-sent] [--acknowledge-duplicates] -o PATH [--force]` | `GET /api/batches/{id}/export` |
| `downcroc job import PATH --account ID [--batch ID] [--on-conflict skip\|error] [--approve none\|all] [--retry-failed] [--requeue-sent] [--acknowledge-duplicates] [--dry-run] [--yes]` | `POST /api/jobs/import` |
| `downcroc job schema [--json]` | `GET /api/jobs/schema` |
| `downcroc account delete ID [--reassign-to NEW] [--force-jobs] [--force-history] [--dry-run] [--yes]` | `DELETE /api/accounts/{id}` |
| `downcroc account archive ID [--yes]` | `POST /api/accounts/{id}/archive` |
| `downcroc account unarchive ID [--yes]` | `POST /api/accounts/{id}/unarchive` |
| `downcroc batch reassign ID --to NEW [--state ...] [--include-failed] [--dry-run] [--yes]` | `POST /api/batches/{id}/reassign` |
| `downcroc batch delete ID [--dry-run] [--yes]` | `DELETE /api/batches/{id}` |
| `downcroc failed forget ID [--yes]` | `DELETE /api/failures/{id}` |
| `downcroc failed purge [--state ...] [--older-than DAYS] [--dry-run] [--yes]` | `POST /api/failures/purge` |
| `downcroc template delete NAME [--yes]` | `DELETE /api/templates/{name}` |
| `downcroc backup delete NAME [--yes]` | `DELETE /api/backups/{name}` |
| `downcroc backup prune --keep N [--dry-run] [--yes]` | `POST /api/backups/prune` |
| `downcroc doctor integrity [--json]` | `GET /api/doctor/integrity` |

All of them support the existing `--json`, `--no-input`, `--wide`, `--full`, and follow the existing non interactive contract: `no_terminal` when a prompt is needed, `confirmation_required` when `--yes` is missing.

## Export bundle

The bundle is a zip so a 10,000 job export stays one file and bodies travel with it.

```
manifest.json
bodies/<job_id>/message.eml
```

`body_ref` points at the rendered MIME message (`jobs/<job_id>/message.eml` in the content store), not at HTML. The bundle carries that file byte for byte, which is what makes a native import faithful and what makes vanilla conversion possible: the exporter parses the MIME back into `to`, `subject`, `text`, `html`, `reply_to`, and attachment parts.

```json
{
  "schema": "downcroc.jobs/v1",
  "exported_at": "2026-10-28T05:40:00Z",
  "exporter_version": "1.0.0rc1",
  "source": {
    "account_id": "acct_old",
    "address": "old@example.com",
    "provider": "generic"
  },
  "selection": {
    "job_ids": [],
    "batch_ids": ["bat_q4"],
    "states": ["queued", "retry_wait"],
    "created_since": "2026-10-20T00:00:00Z",
    "created_until": "2026-10-27T00:00:00Z",
    "include_sent": false
  },
  "batches": [{
    "source_batch_id": "bat_q4",
    "kind": "campaign",
    "name": "Q4 outreach",
    "source_kind": "campaign",
    "source_ref": "q4.csv",
    "source_hash": "sha256:...",
    "schema_version": "downcroc.campaign/v1",
    "campaign_key": "q4",
    "template_ref": "intro",
    "approval": "review",
    "state": "sending",
    "routing": {},
    "options": {},
    "created_at": "2026-10-20T08:00:00Z",
    "approved_at": "2026-10-20T08:05:00Z",
    "counters": {"queued": 120, "sent": 80, "failed": 3}
  }],
  "jobs": [{
    "source_job_id": "job_x",
    "source_batch_id": "bat_q4",
    "recipient": "ana@example.com",
    "recipient_name": "Ana",
    "subject": "Hello",
    "body": {"path": "bodies/job_x/message.eml", "sha256": "...", "bytes": 812},
    "vars": {"company": "Acme"},
    "state": "queued",
    "attempts": 0,
    "next_attempt_at": null,
    "source_kind": "campaign",
    "source_key": "row-2",
    "source_index": 1,
    "step_key": null,
    "parent": null,
    "thread_root": null,
    "created_at": "2026-10-27T10:00:00Z",
    "sent_at": null,
    "last_error_code": null,
    "last_error_message": null,
    "retryable": null
  }],
  "warnings": []
}
```

Selection rules:

- No selector means every job on the account, sent and unsent, plus the batches they belong to.
- `--job` is repeatable and wins over every other filter, so an explicit id is always exported.
- `--batch` is repeatable and selects every job in those batches, regardless of state.
- `--state` is repeatable.
- `--since` and `--until` filter `created_at`, inclusive and exclusive, ISO 8601.
- `--sent-since` and `--sent-until` filter `sent_at`.
- `sent` and `sent_unconfirmed` are included only with `--include-sent`, except when named explicitly with `--job`.
- `sending` is exported with a warning that the job was in flight. Import refuses it by default.
- `--include-batches` writes batch rows even when none of their jobs matched, so a partially exported batch still has its metadata.
- `--vanilla` changes the output format from the native bundle to a `downcroc.campaign/v1` campaign plus attachments, and implies `--include-batches` is irrelevant because batch metadata is not carried.
- `-o -` writes the zip to stdout.
- Export never includes credentials, vault material, daemon tokens, inbound mail, or suppression state. It does include recipients, subjects, bodies, and template variables, so the file is sensitive and is written with `0600` permissions.

## Import rules

1. Verify the zip, the manifest schema, and the sha256 of every body. Abort on any mismatch with `import_checksum_mismatch`. Nothing is written before verification completes.
2. Target batch: `--batch ID` appends into an existing batch on the target account. Otherwise create one batch with `kind` from the manifest, `source_kind=import`, `source_ref` = bundle file name, `source_hash` = sha256 of the zip. Importing the same file twice is refused as `import_duplicate` unless `--on-conflict skip`.
3. Dedupe key is `(batch_id, source_key)` when `source_key` is present, otherwise `(batch_id, recipient, subject, body sha256)`.
4. Mint a new `job.id` and a new `job.message_id`. Keep the old ids in the import batch provenance so a bundle can be traced back.
5. Remap `parent` and `thread_root` inside the bundle. Null and warn when the parent was not exported. Thread continuity with the old mailbox is lost by design.
6. Rewrite `body_ref` into the target content store, verifying the hash again on write.
7. State mapping: `queued`, `awaiting_approval`, `retry_wait` are preserved, unless `--approve none` forces `awaiting_approval` or `--approve all` forces `queued`. `sent` and `sent_unconfirmed` are preserved as history and never re-queued. `sending` is refused with `import_job_in_flight`. `failed` is preserved, and attempts reset to zero only with `--retry-failed`.
8. Rebuild `batch_counters` for every touched batch before returning.
9. Refuse when the target account is pending (`account_pending`) or archived (`account_archived`). Warn when the target daily allowance is below the imported unsent count.
10. Report how many imported recipients are suppressed on the target, without changing suppression.
11. Import is one transaction. Any failure rolls back the batch, the jobs, and the bodies.

## Vanilla conversion

`--vanilla` turns a selection into a plain campaign file that any downcroc install can submit, with no knowledge of this machine and no shared state.

```
campaign.json
attachments/<key>/<file>
```

```json
{
  "schema": "downcroc.campaign/v1",
  "producer": {
    "tool": "downcroc",
    "version": "1.0.0rc1",
    "source": {
      "account": "old@example.com",
      "batch": "bat_q4",
      "exported_at": "2026-10-28T05:40:00Z"
    }
  },
  "campaign": {
    "key": "q4-outreach",
    "name": "Q4 outreach",
    "routing": {"mode": "auto"},
    "options": {
      "approval": "review",
      "suppress_replies": true,
      "reply_window_days": 60,
      "stop_on": ["reply", "bounce"]
    }
  },
  "messages": [{
    "key": "row-2",
    "to": {"email": "ana@example.com", "name": "Ana"},
    "subject": "Hello",
    "text": "Hi Ana,",
    "html": "<p>Hi Ana,</p>",
    "reply_to": null,
    "attachments": ["attachments/row-2/pricing.pdf"]
  }],
  "followups": []
}
```

Rules:

- Built from the rendered MIME, so `text` and `html` are the exact bodies that were queued. Template variables are already baked in and the template itself is not included. If the template is needed, `batch show` still points at `source_ref`.
- `routing.mode` is always `auto` and no account id appears anywhere, so the receiving setup picks its own sender.
- No local ids: no batch id, job id, message id, account id, or absolute path.
- No state, counters, attempts, past send times, or error history. Vanilla means "this is a campaign to run", not "this is a batch with history".
- Attachments are copied into the zip and referenced relatively. A missing attachment aborts with `attachment_missing` instead of silently dropping it.
- Followup steps carry over with `after_days`, `when`, `subject`, `text`, `html`, and `require_approval`.
- The exporter validates the result with the same validator `batch validate` uses and refuses to write a file that would fail on the target, with `vanilla_invalid`.
- Output is `0600`, like the native bundle.
- The receiving side needs nothing but the file:

```sh
unzip q4-vanilla.zip -d q4
downcroc batch validate q4/campaign.json
downcroc batch submit q4/campaign.json
```

- `batch export --vanilla` and `job export --vanilla` produce the same format. A job selection that spans several batches becomes one campaign with a `producer.source.batches` list, and duplicate recipients inside the selection are collapsed with a warning unless `--allow-duplicates` is passed, which sets `campaign.options.allow_duplicates`.

## Duplicate send guard

A vanilla campaign has no per recipient state, so every recipient in it is sendable, including people who were already mailed from the old account. That is the failure this guard exists for.

Triggers:

- `batch export --vanilla` or `job export --vanilla` when the selection contains any `sent` or `sent_unconfirmed` job.
- `job import --requeue-sent`.
- `job export --include-sent` combined with `--vanilla`.

Behavior:

- The daemon returns `duplicate_ack_required` with `sent`, `total`, and the first 10 affected recipients. Nothing is written.
- The CLI prints the warning with the counts, the source address, and the reason, then reads one line. Only `yes` proceeds. `no` aborts with `aborted by user`, exit 1, and no file. Any other input re-asks once and then aborts.
- In non interactive mode `--yes` is not sufficient. `--acknowledge-duplicates` is required, and it is not implied by `--yes`, `--force`, or `--no-input`.
- `--dry-run` prints the warning and the counts without prompting and without writing.
- The guard does not trigger for the native bundle, because native export keeps sent jobs as history and import never re-queues them.

Warning text:

```
warning: this batch already sent 80 of 203 messages from old@example.com
         a vanilla campaign carries no per recipient state, so all 203
         recipients become sendable again, including the 80 already contacted
         message ids and threads will not match the old mailbox
         type yes to continue:
```

## Live reassignment, no bundle

A week long campaign is paced by `sending.daily_allowance`, so the common incident is "the account was banned mid batch", not "move one job". Three levels, one service:

- Batch level: `batch reassign` updates `batch.account_id` and every unsent job in it. This is the incident command. History stays in place, counters stay coherent, and `batch show` still tells one story.
- Account level: `job reassign --account OLD --to NEW` moves every matching unsent job and any batch pin that pointed at OLD.
- Job level: `--job` moves named jobs only.

Rules:

- Only `queued`, `awaiting_approval`, and `retry_wait` move by default. `--include-failed` adds `failed` with attempts reset. `sending` is refused while a lease is live (`job_in_flight`) and is retried after the lease expires.
- `sent`, `sent_unconfirmed`, and `cancelled` never move. They are history.
- Target must exist, must not be the source, and must not be archived. A pending target needs `--force`.
- Rebuild counters for every touched batch. Update `batch.account_id` when it pointed at the source and every one of its jobs moved.
- One transaction, one audit event per moved batch plus a summary event.
- Reassignment never changes `message_id`, `body_ref`, `created_at`, or `source_key`.

## Banned account runbook

Documented in the ticket and in the packaged docs:

1. `downcroc account show OLD` and `downcroc batch list --account OLD` to see what is outstanding.
2. `downcroc batch reassign BAT --to NEW --dry-run`, then run it without `--dry-run`.
3. Work outside any batch: `downcroc job reassign --account OLD --to NEW --dry-run`, then for real.
4. `downcroc account archive OLD --yes` to stop the watcher and keep history, or `downcroc account delete OLD --yes` once no jobs reference it.
5. `downcroc batch show BAT` to confirm counters and the new account.
6. Moving to another machine: `downcroc job export --account OLD -o old.zip`, then `downcroc job import old.zip --account NEW` on the other machine.
7. Handing the campaign to someone else, or to a plain install with no shared state: `downcroc batch export BAT --vanilla -o q4-vanilla.zip`, they unzip it and run `downcroc batch submit q4/campaign.json`. A partially sent batch stops and asks for a typed `yes` first.

## Help and documentation

This feature is destructive and easy to get wrong, so it ships with a guide in both places a user looks.

**Terminal help topic.** Add `jobs` to `TOPICS` in `cli/ui/help.py`, in the same prose style as `accounts` and `batch`, and list it from `downcroc help` with a one line summary. It must render offline, without a daemon, and without touching config or the vault.

The topic covers, in this order:

- what moves and what never moves: `queued`, `awaiting_approval`, `retry_wait` and `failed` with `--include-failed`; never `sent`, `sent_unconfirmed`, `cancelled`
- the three levels: `batch reassign`, `job reassign --account`, `job reassign --job`, and when to use which
- that moving work is never implicit, and that `account delete` needs `--reassign-to` or `--force-jobs`
- export selectors with one example per selector, and that `--job` wins over every filter
- the native bundle layout and what import preserves
- vanilla conversion, the receiving side commands, and what is lost: template, state, counters, Message-IDs, threads
- the duplicate guard, with the exact warning and the rule that `--yes` alone is not enough
- archive versus delete, and what each does to history
- the banned account runbook, the same seven steps as above
- a short error code table for the codes in this ticket

Add `Related:` lines both ways: `jobs` links to `accounts`, `batch`, `send`, `troubleshooting`, and each of those links back to `jobs`.

**Packaged book.** Add `guides/job-portability.md` to the book that ticket 04 builds, linked from the book index, reachable from `docs --list` and search, and packaged into the binary by ticket 06. The page carries the long form of the same material plus the bundle manifest reference, the full error table, and the duplicate guard rationale. It must not require network access.

Neither surface may print credentials, daemon tokens, vault paths, or full message bodies in examples.

## Account deletion

- `GET /api/accounts/{id}/deletion` returns counts and blockers so `--dry-run` and the interactive prompt can show what will happen.
- `DELETE /api/accounts/{id}` refuses with `account_in_use` when jobs exist and `reassign_to` was not given. The hint must name the two real options: `--reassign-to` and `--force-jobs`.
- `--reassign-to NEW` runs the reassign service, then deletes, in one transaction. Moving work is never implicit.
- `--force-jobs` deletes unsent jobs and their bodies, then the account. It refuses when any job is `sending` or `sent` unless `--force-history` is also passed.
- Cascade behavior is unchanged: messages, attempts, activity, quota, and counters go with the account.

## Archive

`POST /api/accounts/{id}/archive` sets a new `archived_at` column, stops the watcher, removes the account from routing and from `account list` unless `--all`, and keeps every job, message, and counter. `unarchive` restores it. This is the recommended path for a banned mailbox whose history matters.

## Audit events

`job.exported`, `job.imported`, `job.deleted`, `job.cancelled`, `job.reassigned`, `batch.reassigned`, `batch.deleted`, `account.archived`, `account.deleted`, `backup.pruned`, `backup.deleted`, `template.deleted`, `failures.purged`. Structured fields only: ids, counts, channel, never recipients or bodies.

## Errors

New codes, each with a hint:

- `job_in_flight`
- `job_not_terminal`
- `job_state_conflict`
- `batch_state_conflict`
- `import_invalid`
- `import_checksum_mismatch`
- `import_duplicate`
- `import_job_in_flight`
- `vanilla_invalid`
- `attachment_missing`
- `duplicate_ack_required`
- `reassign_same_account`
- `reassign_target_invalid`
- `account_pending`
- `account_archived`
- `backup_not_found`
- `template_not_found`

## Migration

One Alembic revision: `accounts.archived_at` nullable timestamp, plus `ix_jobs_batch_created` on `(batch_id, created_at)` for selection. No backfill. The daemon still runs `upgrade head` at startup.

## Tests

Black box acceptance in `tests/`. Fake only SMTP, IMAP, and OAuth at the network boundary. Real daemon, real SQLite, real content store.

- Export all from an account, delete it, import into a second account, assert counts, states, subjects, bodies, and counters.
- Export one job by id, one batch by id, and a `created_at` window, asserting the exact selection.
- Import the same bundle twice with `--on-conflict skip` and assert idempotency.
- Import a bundle with a corrupted body and assert refusal and full rollback.
- Export a partially sent batch as vanilla, submit the result on a second isolated daemon home with no shared state, and assert recipient count, subjects, and bodies match.
- Assert the vanilla file contains no account id, batch id, job id, message id, absolute path, state, or counter.
- Assert a partially sent vanilla export refuses without `--acknowledge-duplicates`, refuses `--yes` alone in non interactive mode, and aborts on a typed `no`.
- Assert `--dry-run` prints the duplicate warning and writes nothing.
- Assert `downcroc help jobs` renders with no daemon and no network, appears in the `downcroc help` index, and that its `Related:` topics all resolve.
- Assert the packaged book contains `guides/job-portability.md`, that the book index links it, and that `docs --list` and search reach it.
- Batch reassign mid flight: queued jobs move, sent jobs stay, counters match.
- Account delete without `--reassign-to` fails, with it succeeds, and `--force-jobs` removes only unsent jobs.
- Job delete on a terminal job, refusal on a queued job, success with `--force`.
- Batch delete on a cancelled batch, refusal on a sending batch.
- Archive hides from list and routing, unarchive restores.
- Every destructive CLI command without `--yes` returns `confirmation_required` and no prompt hangs under `CI=1` with piped stdin.
- Every CLI command has a matching endpoint test.

## Out of scope

- Moving inbound mail or suppression between accounts.
- Preserving Message-ID or thread continuity across accounts.
- Cross machine sync, a server side job store, or a shared queue.
- Per job scheduled send times beyond the existing daily allowance and window.
- macOS.

## Checklist

- [ ] `job cancel` cancels one job through `POST /api/jobs/{id}/cancel`
- [ ] `job delete` removes a terminal job and its body, and refuses a live job without `--force`
- [ ] `job delete` refuses `sending` jobs even with `--force`
- [ ] `batch delete` removes a cancelled or done batch with its jobs, counters, and bodies, and refuses `sending`
- [ ] `failed forget` and `failed purge` remove failure rows through the API
- [ ] `template delete` and `backup delete` and `backup prune` exist and are daemon driven
- [ ] `GET /api/accounts/{id}/deletion` reports jobs, batches, messages, attempts, activity, and blockers
- [ ] `account delete` without `--reassign-to` and without `--force-jobs` still fails, and the hint names both real options
- [ ] `account delete --reassign-to NEW` moves matching jobs and deletes in one transaction
- [ ] `account delete --force-jobs` removes unsent jobs only, and `--force-history` is required to remove sent history
- [ ] `account archive` and `account unarchive` exist, and an archived account is out of routing and out of the default list
- [ ] `batch reassign` moves the batch pin and its unsent jobs, leaves sent jobs, and rebuilds counters
- [ ] `job reassign --account` moves unsent jobs, honours `--state`, `--since`, `--until`, and `--job`
- [ ] Reassignment refuses `sending` jobs, the same account, archived targets, and pending targets without `--force`
- [ ] Reassignment never changes `message_id`, `body_ref`, `created_at`, or `source_key`
- [ ] `job export` with no selector exports every job and its batches
- [ ] `job export --job` exports exactly the named jobs, even when another filter would exclude them
- [ ] `job export --batch` exports every job in the batch
- [ ] `job export --state`, `--since`, `--until`, `--sent-since`, and `--sent-until` select the documented rows
- [ ] `sent` jobs are exported only with `--include-sent` or when named explicitly
- [ ] The bundle is a zip with `manifest.json` and `bodies/<job_id>/message.eml`, written `0600`, with a per body sha256
- [ ] `job import` creates or appends to a batch, mints new job ids and Message-IDs, remaps parents, and rewrites `body_ref`
- [ ] `job import --batch` appends into an existing batch on the target account
- [ ] Import verifies every checksum before writing and rolls back completely on failure
- [ ] Import is idempotent by `source_hash` and `(batch_id, source_key)`, and `--on-conflict skip` reports the duplicates
- [ ] Import refuses `sending` jobs, pending targets, and archived targets, and reports suppressed recipients
- [ ] Import rebuilds counters for every touched batch
- [ ] `job schema` prints the bundle manifest schema from the daemon
- [ ] `batch export --vanilla` writes `campaign.json` plus `attachments/` and the result passes `batch validate` on a clean install
- [ ] Vanilla output contains no account id, batch id, job id, message id, absolute path, state, counter, or credential
- [ ] Vanilla output preserves text, html, reply_to, attachments, and followup steps, and refuses with `attachment_missing` when an attachment file is gone
- [ ] A vanilla export of a partially sent batch prints the duplicate warning and requires a typed `yes`
- [ ] In non interactive mode `--yes` alone is refused and `--acknowledge-duplicates` is required, and the API enforces the same gate with `duplicate_ack_required`
- [ ] `--dry-run` prints the duplicate warning and writes nothing
- [ ] Vanilla export of a multi-batch selection collapses duplicate recipients with a warning, and `--allow-duplicates` keeps them
- [ ] A vanilla campaign exported from one install submits and sends on a second install with no shared state
- [ ] `downcroc help jobs` exists, is listed by `downcroc help`, renders offline with no daemon, and covers moves, export, import, vanilla, the duplicate guard, archive, and the runbook
- [ ] The `jobs` topic cross-links `accounts`, `batch`, `send`, and `troubleshooting`, and each of those links back to `jobs`
- [ ] The packaged book contains `guides/job-portability.md`, linked from the index, reachable from `docs --list` and search, and included in the frozen artifact
- [ ] Neither the help topic nor the book page prints credentials, tokens, vault paths, or full message bodies
- [ ] `doctor integrity` reports missing bodies, orphaned content files, and counter drift
- [ ] Every action in this ticket writes a structured audit event without recipients or bodies
- [ ] Every CLI command is a thin client with a matching API endpoint, and no CLI path touches SQLite or the content store
- [ ] All destructive commands support `--dry-run` where meaningful and require `--yes` in non interactive mode
- [ ] The banned account runbook is covered by an acceptance test that reassigns a mid flight batch and confirms the counters
- [ ] macOS is untouched

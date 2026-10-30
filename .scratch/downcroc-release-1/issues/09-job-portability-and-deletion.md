# 09 - Sender policy, attempts, and deletion lifecycle

**What to build:** stop letting a job own its sender. A campaign job is an obligation to deliver a message, not a commitment to send it from one mailbox. Split the sender out of the job into a policy, create the attempt record that ticket 13 extends, and make account deletion and reassignment correct under both policies.

Phase A is already committed as `df92ca7`: job cancel and delete, batch delete, failure purge, account archive, live reassignment, and the deletion preview. This ticket finishes the model underneath those controls.

**Blocked by:** nothing. The export bundle, import, and vanilla conversion are removed from release 1. They existed to move work off a banned mailbox, and ticket 13's auto routing solves that inside the daemon. Whole-home backup already covers moving to another machine.

**Status:** ready-for-agent

## Ownership rule

Daemon:

- Owns the policy, the attempt row, deletion semantics, and every event.
- Never moves a pinned job implicitly. It reports the hold.

CLI:

- Flags in, HTTP out, render the response.
- The interactive flow uses the same endpoints.

## Sender policy

| Value | Meaning | `account_id` |
|---|---|---|
| `pinned` | The job must come from one named mailbox | set |
| `auto` | The daemon chooses an eligible mailbox at send time | null |

- Manual jobs and single sends default to `pinned`, because a human sending one message expects the mailbox they chose.
- Campaign jobs become `auto` when ticket 13 lands fleet scheduling. Until then `batch submit` keeps resolving one account and writes `pinned`, so no job can be created that no scheduler can pick.
- `job reassign --unpin` converts a selection to `auto` and clears `account_id`. `--pin` converts a selection to `pinned` on the target account.
- The mechanism (SMTP or Gmail API) is never on the job and never on the account. It is chosen per attempt, and ticket 13 owns it.

## `send_attempts`

Created by this ticket. It is the only record of which mailbox actually carried a message.

| Column | Type | Notes |
|---|---|---|
| `id` | text | `att_...` |
| `job_id` | text FK | `ondelete="CASCADE"` |
| `account_id` | text FK nullable | `ondelete="SET NULL"`, the mailbox that attempted |
| `transport` | text | `smtp` or `gmail_api`, copied so history survives binding deletion |
| `started_at`, `finished_at` | timestamp | |
| `outcome` | text | `sent`, `failed`, `deferred`, `uncertain` |
| `accepted` | bool nullable | true, false, or unknown |
| `error_code`, `error_message` | text nullable | redacted |
| `provider_message_id` | text nullable | provider id when known |
| `detail` | text nullable | JSON, redacted |

Index on `(job_id, started_at)`. `account_id` is nullable and `SET NULL` because an attempt is history and must outlive a deleted mailbox without blocking the delete.

Ticket 13 adds `binding_id` only. Ticket 14 adds `quota_day` and `quota_state` only.

## Schema

One Alembic revision after `a4d8e2f6c9b3`:

- `jobs.sender_policy` text, not null, default `pinned`.
- `jobs.account_id` altered to nullable with `ondelete="SET NULL"`.
- Check constraint: `(sender_policy = 'pinned' AND account_id IS NOT NULL) OR (sender_policy = 'auto' AND account_id IS NULL)`.
- `send_attempts` created as above.
- Backfill: every existing job becomes `pinned` with its current account.
- `batches.account_id` is already nullable and stays as is.

`jobs.batch_id` stays NOT NULL. Every job belongs to a batch, including manual jobs.

## Auto dispatch

An auto job has no account, so `JobRepo.due(account_id, now)` cannot return it. Add a fleet query:

- `due_auto(now, limit)` returns `queued` or `retry_wait` auto jobs whose retry clock has expired, plus `sending` auto jobs whose lease has expired.
- The dispatcher builds one shared auto pool per cycle. Each eligible account may claim from it, and a claimed job leaves the pool.
- The account is passed to `OutboundService.deliver` as an argument. The job row stays null, because the attempt records the mailbox.
- A failed auto job returns to `retry_wait` with a null account and is eligible for any mailbox on the next cycle.

Ticket 13 replaces the pool with binding-aware capacity and failover. The query shape stays.

## Reassignment

Only pinned jobs move by default. An auto job has no sender to move, so it is reported as `already_auto` and the command still succeeds when other jobs moved.

- `--pin` converts the selection to `pinned` on the target account.
- `--unpin` converts the selection to `auto` and clears `account_id`. It does not need a target.
- A pinned job whose target is the source is refused with `reassign_same_account`, unless `--unpin` was passed.
- Only `queued`, `awaiting_approval`, and `retry_wait` move. `--include-failed` adds `failed` with attempts reset. `sending` is refused with `job_in_flight`.
- `sent`, `sent_unconfirmed`, and `cancelled` never move.
- Target must exist, must not be the source, and must not be archived. A pending target needs `--force`.
- Rebuild counters for every touched batch. Update `batch.account_id` when it pointed at the source and every pinned job moved.
- Reassignment never changes `message_id`, `body_ref`, `created_at`, or `source_key`. Attempt history is never rewritten.

## Account deletion

- `GET /api/accounts/{id}/deletion` returns `pinned_jobs`, `auto_jobs`, `batches_pinned`, `messages`, `attempts`, `activity`, and `quota`.
- `DELETE /api/accounts/{id}` refuses with `account_in_use` only when pinned jobs exist and neither `reassign_to` nor `force_jobs` was given. Auto jobs never block a delete.
- Auto jobs are detached and keep routing. They are not deleted and not reassigned.
- `--reassign-to NEW` moves pinned work, then deletes, in one transaction.
- `--force-jobs` deletes unsent pinned jobs and their bodies, then the account. It refuses when any pinned job is `sending` or `sent` unless `--force-history` is also passed.
- `send_attempts.account_id` is `SET NULL`, so attempt rows survive the mailbox.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/jobs/{job_id}/attempts` | Attempt history, oldest first |
| POST | `/api/jobs/reassign` | Move or repin jobs |
| GET | `/api/accounts/{account_id}/deletion` | Counts split by policy |
| DELETE | `/api/accounts/{account_id}` | Delete with `reassign_to` or `force_jobs` |

Reassign request adds `pin` and `unpin`. `to_account_id` is optional when `unpin` is true and required otherwise. Response adds `unpinned` and `pinned` counts.

Every job payload carries `sender_policy` and a nullable `account_id`. No endpoint returns or accepts a transport on a job.

The attempts response carries `account_id`, `transport`, `outcome`, `accepted`, `error_code`, `provider_message_id`, and timestamps. It never returns credentials.

## CLI

| Command | Endpoint |
|---|---|
| `downcroc job reassign --to ID [--pin]` | `POST /api/jobs/reassign` |
| `downcroc job reassign --unpin [--job ID]` | `POST /api/jobs/reassign` |
| `downcroc job attempts ID [--json]` | `GET /api/jobs/{id}/attempts` |
| `downcroc account deletion ID` | `GET /api/accounts/{id}/deletion` |

- `job show` prints `sender: pinned acct_x` or `sender: auto`.
- `account deletion` prints the pinned and auto split and the blockers.
- The interactive reassign card offers pin and unpin, and explains that unpinned work is routed at send time.

## Help

Add `jobs` to `TOPICS` in `cli/ui/help.py`, listed from `downcroc help`. It renders offline, without a daemon or vault, and covers:

- what moves and what never moves
- `pinned` versus `auto`, and why a campaign is auto
- the three reassignment levels and `--pin` / `--unpin`
- that account deletion blocks on pinned work only
- archive versus delete

Add `Related:` lines both ways to `accounts`, `batch`, and `send`.

## Audit events

`job.reassigned`, `job.pinned`, `job.unpinned`, `account.deleted`. Structured fields only: ids, counts, sender policy. Never recipients, bodies, tokens, or credentials.

## Errors

- `job_in_flight` (409)
- `reassign_same_account` (409)
- `reassign_target_invalid` (409)
- `account_in_use` (409), hint naming `--reassign-to` and `--force-jobs`
- `sender_conflict` (422), when `--pin` and `--unpin` are both passed, or `--unpin` carries a target

## Tests

One black-box scenario, because the ticket is now a model change plus deletion semantics:

- Submit two pinned jobs. Unpin one and assert it becomes `auto` with `account_id` null and still sends.
- Delete the source account without options and assert `account_in_use` naming the pinned job.
- Delete with `--reassign-to` and assert the pinned job moved, the auto job survived detached, the counters match, and the auto job still sends.

No existing test is deleted or weakened.

## Out of scope

- Export and import bundles.
- Vanilla campaign conversion and the duplicate guard.
- Moving to another machine. Backup and restore covers it.
- Per-attempt credentials, bindings, and transport selection. Ticket 13.
- Pause, quota reservations, and capacity. Ticket 14.
- macOS.

## Checklist

- [ ] `jobs.sender_policy` exists with `pinned` and `auto`, and a check constraint ties it to `account_id`
- [ ] `jobs.account_id` is nullable with `SET NULL`
- [ ] `send_attempts` exists with the documented columns and index
- [ ] Every existing job is backfilled as pinned
- [ ] An auto job has a null account and is dispatched from the fleet pool
- [ ] `--pin` and `--unpin` convert the selection and emit events
- [ ] Reassigning an auto job without `--pin` reports `already_auto`
- [ ] Account deletion blocks on pinned jobs only
- [ ] Auto jobs survive account deletion detached and keep routing
- [ ] `--reassign-to` moves pinned work before deleting
- [ ] `job show`, `job list`, and the attempts endpoint report the policy
- [ ] `downcroc help jobs` renders offline
- [ ] One scenario test covers pin, unpin, blocked delete, reassign, and auto survival

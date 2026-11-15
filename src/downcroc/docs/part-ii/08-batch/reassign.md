---
title: batch reassign and delete
commands: [batch.reassign, batch.delete]
flags: [--to, --state, --include-failed, --dry-run, batch.reassign batch_id, batch.delete batch_id]
concepts: [batch, job]
screens: []
---

# batch reassign and delete

`batch reassign` moves jobs in a [[batch]] to another account. `batch delete` removes a finished batch and its jobs. These commands affect batch-scoped work; for finer-grained moves, pinning/unpinning, or job-level selection across batches, see `downcroc job reassign`.

## Usage

```text
downcroc batch reassign <batch_id> --to TO_ACCOUNT_ID [--state STATE] [--include-failed] [--dry-run] [--yes]
downcroc batch delete <batch_id> [--dry-run] [--yes]
```

## Commands

### reassign

Moves a batch’s jobs to another account.

```text
downcroc batch reassign <batch_id> --to TO_ACCOUNT_ID [--state STATE] [--include-failed] [--dry-run] [--yes]
```

- `--to TO_ACCOUNT_ID` (required) is the target account id to receive the jobs.
- `--state STATE` filters which jobs to move by state; it can be repeated to include several states. Allowed states: `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.
- `--include-failed` moves failed jobs as well. By default, failed jobs are excluded unless explicitly included.
- `--dry-run` reports what would move without making changes.
- Without `--dry-run`, the command asks for confirmation (stating the batch and target account) unless `--yes` is given.

**Behavior and constraints**

- Reassignment moves eligible jobs in the batch to the target account according to the selection and system rules. Jobs that cannot be moved in their current state or under current constraints are skipped and reported with a reason (for example, jobs that are in flight or otherwise not movable at that time). Counts of moved jobs and any skipped jobs/reasons are reported.
- Batch-level reassignment is about moving jobs to a target account; it does not expose pin/unpin routing modes. For pinning/unpinning or selecting specific jobs across accounts/batches, use `downcroc job reassign`.

**Output**

- Default: reports how many jobs would be or were moved and lists skipped jobs with reasons.
- With `--json`: prints the full reassignment result (including dry-run flag, counts, and skipped items).

### delete

Deletes a finished batch.

```text
downcroc batch delete <batch_id> [--dry-run] [--yes]
```

- Deletes the specified batch and its jobs. This is intended for batches that have reached a finished state; batches that are not eligible for deletion are rejected.
- `--dry-run` reports what would be deleted (the batch and how many jobs) without making changes.
- Without `--dry-run`, asks for confirmation unless `--yes` is given.

**Output**

- Default: reports that the batch (and its jobs) would be or were deleted.
- With `--json`: prints the deletion result.

## Options

`--to TO_ACCOUNT_ID`
: Target account id for `batch reassign` (required).

`--state STATE`
: Job state filter for `batch reassign` (repeatable): `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.

`--include-failed`
: Include failed jobs when reassigning.

`--dry-run`
: Report what would move or be deleted without making changes.

`--yes`
: Skip the confirmation prompt (where confirmation applies).

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch reassign bat_123 --to acct_456` — move a batch’s jobs to another account (after confirmation).
- `downcroc batch reassign bat_123 --to acct_456 --state queued --state retry_wait --dry-run` — preview moving only queued/retry-wait jobs.
- `downcroc batch reassign bat_123 --to acct_456 --include-failed --yes` — move jobs including failed ones without prompting.
- `downcroc batch delete bat_123 --dry-run` — preview deleting a finished batch.
- `downcroc batch delete bat_123 --yes` — delete a finished batch.

## See also

- [inspect.md](inspect.md) — inspect a batch and its jobs
- [holds.md](holds.md) — pause/resume a batch
- [approve.md](approve.md) — approve or cancel a batch
- [../09-job/job.md](../09-job/job.md) — job-level reassign, pin/unpin, and delete
- [../07-account/account.md](../07-account/account.md) — manage accounts
- [../part-i/04-mailboxes/move-and-pin.md](../part-i/04-mailboxes/move-and-pin.md) — moving and pinning work
- [../19-logs/events/jobs-dispatch.md](../19-logs/events/jobs-dispatch.md) — job/batch log events
- [../part-iii/33-states.md](../part-iii/33-states.md) — batch and job states

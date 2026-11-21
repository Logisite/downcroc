---
title: failed
commands: [failed, failed.list, failed.show, failed.retry, failed.retry-all, failed.forget, failed.purge]
flags: [--limit, --offset, --state, --older-than, --dry-run]
concepts: [failed, job]
screens: []
---

# failed

`failed` lets you inspect and act on [[failed]] jobs — jobs that could not be sent successfully and were recorded as failures. Each failure carries a reason [[code]] and message. From here you can list and examine failures, retry them, forget individual failures, or purge failures in bulk.

A failure record is tied to a job (and its batch/account/recipient, error code and message, retryability, attempt count, and failure time). Retrying asks downcroc to try the job again; forgetting/purging removes failure records without sending.

## Usage

```text
downcroc failed <action> [options]
```

Actions: `list`, `show`, `retry`, `retry-all`, `forget`, `purge`.

## Actions

### list

Lists failed jobs.

```text
downcroc failed list [--limit LIMIT] [--offset OFFSET]
```

- Returns failed jobs in the failure list. Default limit is 100 (1–500). `--offset` skips rows for paging. Failures are newest first by default; `--oldest-first` puts the oldest first. `[cli] list_order = "oldest_first"` changes the default.
- **Output:** by default prints a table of job id, recipient, code, attempts, failed time, and message, and a page footer when results are paged/truncated. With `--json`, prints the failure records as JSON.

### show

Shows one failure in detail.

```text
downcroc failed show <job_id>
```

- Displays the failure for `job_id`: job, batch, account, recipient, code, message, whether it is retryable, attempt count, and when it failed.
- With `--json`, prints the failure record as JSON.

### retry

Retries one failed job.

```text
downcroc failed retry <job_id>
```

- Requests a retry of the specified failed job. On success the job is reset for retry (and the batch may be moved back to sending if it had completed, depending on state); see failure/job behavior in the system.
- **Output:** prints the retried job id and its state (or the job as JSON with `--json`).

### retry-all

Retries every failure currently recorded.

```text
downcroc failed retry-all [--yes]
```

- Looks up the current failures and retries them. Before acting it summarizes how many failures there are, how many accounts they span, and how many of the shown failures are marked retryable.
- Asks for confirmation unless `--yes` is given (or confirmation is satisfied per `--no-input` rules).
- If there are no failures, it reports that there is nothing to retry.
- **Output:** prints how many failures were retried (or JSON with the count).

### forget

Forgets one failure record.

```text
downcroc failed forget <job_id> [--yes]
```

- Removes the failure record for `job_id` from the failure set (it does not send the job). Asks for confirmation unless `--yes` is given.
- **Output:** prints that the failure was forgotten (or JSON with the result).

### purge

Forgets failures in bulk by state and/or age.

```text
downcroc failed purge [--state STATE] [--older-than DAYS] [--dry-run] [--yes]
```

- Selects failures to purge based on the provided filters:
  - `--state {queued,awaiting_approval,sending,sent,sent_unconfirmed,retry_wait,failed,cancelled}` filters by job state; the option can be repeated to include several states.
  - `--older-than DAYS` limits to failures older than the given number of days.
- `--dry-run` reports how many failures would be forgotten without making changes.
- Without `--dry-run`, purging requires confirmation unless `--yes` is given.
- **Output:** prints how many failures would be or were forgotten (or JSON with the result).

## Options

`--limit LIMIT`
: Maximum rows to return for `list` (1–500, default 100).

`--offset OFFSET`
: Rows to skip for `list`.

`--state STATE`
: Job state filter for `purge` (repeatable): `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.

`--older-than DAYS`
: Age filter for `purge`, in days.

`--dry-run`
: With `purge`, report what would be forgotten without changing anything.

`--yes`
: Skip the confirmation prompt for `retry-all`, `forget`, and `purge` (where confirmation applies).

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc failed list` — list recent failures.
- `downcroc failed show job_123` — show details for one failed job.
- `downcroc failed retry job_123` — retry a failed job.
- `downcroc failed retry-all --yes` — retry every recorded failure.
- `downcroc failed forget job_123 --yes` — remove a failure record without retrying.
- `downcroc failed purge --state failed --older-than 30 --dry-run` — preview purging failed records older than 30 days.

## See also

- [../09-job/job.md](../09-job/job.md) — inspect and manage individual jobs
- [../08-batch/inspect.md](../08-batch/inspect.md) — inspect batches and their jobs
- [../02-status/status.md](../02-status/status.md) — recent failures in the overall status
- [../19-logs/logs.md](../19-logs/logs.md) — read the daemon log for failure detail
- [../19-logs/events/failures.md](../19-logs/events/failures.md) — log events for failures and retries
- [../part-i/03-keeping-it-running/problems-list.md](../part-i/03-keeping-it-running/problems-list.md) — reading problems in order
- [../part-iii/32-failures.md](../part-iii/32-failures.md) — failure concepts
- [../part-iii/33-states.md](../part-iii/33-states.md) — job states

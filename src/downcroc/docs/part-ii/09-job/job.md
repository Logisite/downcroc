---
title: job
commands: [job, job.list, job.show, job.send, job.pause, job.resume, job.cancel, job.delete, job.reassign, job.attempts, job.create]
flags: [job.create --account, job.list --account, job.reassign --account, job.attempts --addresses, job.show --addresses, job.create --batch, job.list --batch, job.reassign --batch, job.delete --dry-run, job.reassign --dry-run, job.create --force, job.delete --force, job.create --html, job.create --html-file, job.reassign --include-failed, job.reassign --job, job.list --limit, job.create --name, job.list --offset, job.reassign --pin, job.pause --reason, job.resume --reason, job.create --send, job.reassign --since, job.list --state, job.reassign --state, job.create --subject, job.create --text, job.create --text-file, job.create --to, job.reassign --to, job.reassign --until]
concepts: [job]
screens: []
---

# job

`job` lets you inspect and manage individual send [[job]]s: list and view them, send one now, pause or resume, cancel or delete, reassign or (un)pin them between accounts, inspect send attempts, and create a manual job.

Jobs belong to batches and are sent from accounts according to state, policy, and holds. Some actions only apply in certain states (for example, a job that is in flight cannot be paused; a queued job can be cancelled; deletion rules differ for terminal vs non-terminal states).

## Usage

```text
downcroc job <action> [options]
```

Actions: `list`, `show`, `send`, `pause`, `resume`, `cancel`, `delete`, `reassign`, `attempts`, `create`.

## Listing and inspecting

### list

Lists jobs.

```text
downcroc job list [--batch BATCH] [--account ACCOUNT] [--state STATE] [--limit LIMIT] [--offset OFFSET]
```

- Filters: `--batch` by batch id, `--account` by account id, `--state` by job state. `--limit` sets maximum rows (1–500, default 100) and `--offset` skips rows for paging.
- Job states: `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.
- **Output:** prints a job list (and page footer when paged). With `--json`, prints jobs as JSON.

### show

Shows one job.

```text
downcroc job show <job_id> [--addresses]
```

- Displays the job’s details and current state (including sender/routing information as applicable).
- `--addresses` shows account addresses instead of account ids in the output.
- With `--json`, prints the job as JSON.

### attempts

Shows the send attempts for a job.

```text
downcroc job attempts <job_id> [--addresses]
```

- Lists recorded send attempts for the job. If there are no attempts yet, it reports that.
- `--addresses` shows account addresses instead of ids.
- With `--json`, prints attempts as JSON.

## Acting on a job

### send

Sends one job now.

```text
downcroc job send <job_id> [--yes]
```

- Requests an immediate send of the specified job. Before sending, it confirms (showing recipient, subject, and sender in interactive mode) unless `--yes` is given or confirmation is satisfied per `--no-input` rules.
- **Output:** prints the job id and resulting state (or JSON with `--json`).

### pause

Pauses one job.

```text
downcroc job pause <job_id> [--reason REASON]
```

- Pauses the job so it is held and not dispatched while paused. `--reason` records why it is paused.
- A job that is currently in flight/sending cannot be paused in that moment; jobs can only be paused in states that allow it (otherwise the request is rejected). See hold behavior and job states.
- **Output:** prints the job id, state, and action (or JSON).

### resume

Resumes one paused job.

```text
downcroc job resume <job_id> [--reason REASON]
```

- Clears the job-level pause so it can proceed according to normal scheduling/holds. `--reason` can record why it was resumed.
- **Output:** prints the job id, state, and action (or JSON).

### cancel

Cancels one queued job.

```text
downcroc job cancel <job_id>
```

- Cancels the specified job (intended for jobs in a cancellable/queued state; requests that are not valid for the job’s state are rejected).
- **Output:** prints the job id and state (or JSON).

### delete

Deletes one job.

```text
downcroc job delete <job_id> [--force] [--dry-run] [--yes]
```

- Deletes the job. `--dry-run` reports what would be deleted without making changes.
- Deletion of a job that has not reached a terminal state may require `--force` (depending on state/rules).
- Without `--dry-run`, asks for confirmation unless `--yes` is given.
- **Output:** prints whether the job would be or was deleted, with its id and state (or JSON).

## Reassigning, pinning, and routing

### reassign

Moves jobs between accounts, and can pin or unpin their sender routing.

```text
downcroc job reassign [selection] [--to TO_ACCOUNT_ID] [--pin | --unpin] [--include-failed] [--dry-run] [--yes]
```

This command operates on a selection of jobs and can change which account they are assigned to and/or whether they are pinned to an account or routed at send time.

**Selecting jobs**

You can scope the selection with one or more of:
- `--account FROM_ACCOUNT_ID` — source account.
- `--to TO_ACCOUNT_ID` — target account (required when moving/pinning to a target; omit when unpinning to route at send time).
- `--job JOB_IDS` — specific job id (repeatable).
- `--batch BATCH_IDS` — batch id (repeatable).
- `--state STATE` — job state filter (repeatable): `queued`, `awaiting_approval`, `sending`, `sent`, `sent_unconfirmed`, `retry_wait`, `failed`, `cancelled`.
- `--since SINCE` / `--until UNTIL` — created on/after or before a timestamp.
- `--include-failed` — include failed jobs in the move (failed jobs are excluded unless requested).

**Pinning and routing**

- `--pin` pins the selected jobs to the target account (so they send from that account).
- `--unpin` removes pinning so the jobs are routed at send time. `--to` is omitted when unpinning. `--pin` and `--unpin` are mutually exclusive.
- Without `--pin`/`--unpin`, the command moves the selection to the target account (as applicable to the selection/routing mode).

**Execution and safety**

- `--dry-run` reports what would move/change without making changes.
- Without `--dry-run`, asks for confirmation unless `--yes` is given. The confirmation describes the action (move to target, pin to target, or route at send time).
- **Output:** reports how many jobs would be or were moved, in how many batches, counts pinned/unpinned, and any jobs skipped with reasons (or JSON with the full result).

Reassignment respects job/batch state and in-flight constraints; jobs that cannot be moved or changed in their current state are skipped with a reason.

## Creating a manual job

### create

Creates a manual job.

```text
downcroc job create --account ACCOUNT_ID --to RECIPIENT --subject SUBJECT
                   [--name RECIPIENT_NAME]
                   [--text TEXT | --text-file TEXT_FILE]
                   [--html HTML | --html-file HTML_FILE]
                   [--batch BATCH] [--send] [--force] [--yes]
```

- **Required:** `--account` (sending account id), `--to` (recipient address), `--subject` (subject line). Provide a body as plain text (`--text` or `--text-file`) and/or HTML (`--html` or `--html-file`); files are read from the given paths.
- `--name` sets the recipient name.
- `--batch` groups the job under an existing batch id.
- **Account state:** before creating, downcroc checks the sending account. If the account is not connected, creation/send will wait until it connects; `--force` allows queuing even when the account is not connected (a warning is shown in interactive output).
- `--send` sends the job immediately after creating it. When sending, it confirms (showing recipient, subject, sender) unless `--yes` is given or confirmation is satisfied per `--no-input` rules.
- **Output:** prints the created job id and state (or JSON). If sent immediately, reports the resulting state.

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc job list --state queued` — list queued jobs.
- `downcroc job list --batch <batch_id> --limit 50` — list jobs in a batch.
- `downcroc job show job_123` — show a job.
- `downcroc job attempts job_123` — show send attempts for a job.
- `downcroc job send job_123` — send a job now (with confirmation).
- `downcroc job pause job_123 --reason "hold for review"` — pause a job.
- `downcroc job resume job_123` — resume a paused job.
- `downcroc job cancel job_123` — cancel a queued job.
- `downcroc job delete job_123 --dry-run` — preview deleting a job.
- `downcroc job reassign --account acct_a --to acct_b --state queued --dry-run` — preview moving queued jobs to another account.
- `downcroc job reassign --job job_123 --to acct_b --pin --yes` — pin a job to a specific account.
- `downcroc job reassign --job job_123 --unpin --yes` — unpin a job so it routes at send time.
- `downcroc job create --account acct_1 --to alice@example.com --subject "Hello" --text "Hi Alice"` — create a manual job.
- `downcroc job create --account acct_1 --to alice@example.com --subject "Hello" --text-file body.txt --send` — create and send immediately.

## See also

- [../10-failed/failed.md](../10-failed/failed.md) — inspect and retry failed jobs
- [../08-batch/inspect.md](../08-batch/inspect.md) — inspect batches and their jobs
- [../08-batch/reassign.md](../08-batch/reassign.md) — reassign/delete work at batch scope
- [../08-batch/holds.md](../08-batch/holds.md) — hold and release work
- [../07-account/account.md](../07-account/account.md) — accounts and send policy
- [../19-logs/logs.md](../19-logs/logs.md) — read the daemon log
- [../19-logs/events/jobs-dispatch.md](../19-logs/events/jobs-dispatch.md) — job and dispatch log events
- [../part-iii/33-states.md](../part-iii/33-states.md) — job states
- [../part-i/04-mailboxes/move-and-pin.md](../part-i/04-mailboxes/move-and-pin.md) — moving and pinning work between mailboxes

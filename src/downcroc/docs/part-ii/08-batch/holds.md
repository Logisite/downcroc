---
title: batch holds
commands: [batch.pause, batch.resume]
flags: [--all, --reason, batch.pause batch_id, batch.resume batch_id]
concepts: [batch]
screens: []
---

# batch holds

`batch pause` and `batch resume` control batch-level [[hold]]s. Pausing a batch holds its work so it is not dispatched while paused; resuming clears that hold. This is different from cancelling a batch (which stops it) and from pausing at the service, account, or job level.

## Usage

```text
downcroc batch pause [batch_id] [--all] [--reason REASON]
downcroc batch resume [batch_id] [--all] [--reason REASON]
```

## Commands

### pause

Pauses one batch or every existing batch.

```text
downcroc batch pause [batch_id] [--all] [--reason REASON]
```

- To pause a specific batch, provide `batch_id`. To pause every existing batch, pass `--all` (a batch id is not required when `--all` is used).
- `--reason REASON` records why sending is paused.
- If neither a `batch_id` nor `--all` is provided, the command fails with a usage error indicating that an id or `--all` is required.

Pausing affects batches in states where a pause applies (for example active/sending or awaiting-approval batches); batches that cannot be paused in their current state are not changed in that way.

**Output**

- For a single batch: reports the batch id, action, and whether it changed (or JSON with the result).
- With `--all`: reports how many batches were affected (paused/skipped as applicable) and the action (or JSON with the result).

### resume

Resumes one paused batch or every paused batch.

```text
downcroc batch resume [batch_id] [--all] [--reason REASON]
```

- To resume a specific batch, provide `batch_id`. To resume every paused batch, pass `--all`.
- `--reason REASON` can record why sending is resumed.
- If neither a `batch_id` nor `--all` is provided, the command fails with a usage error indicating that an id or `--all` is required.

**Output**

- For a single batch: reports the batch id, action, and whether it changed (or JSON).
- With `--all`: reports how many batches were resumed (or JSON).

## Options

`--all`
: Apply to every existing batch (`pause`) or every paused batch (`resume`) instead of a single batch id.

`--reason REASON`
: Why sending is paused or resumed.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Notes

A batch-level hold is one layer of control. Work may also be held at the service, account, or job level, or gated by approval/state and policy; a batch must be unpaused and otherwise eligible for its jobs to proceed. Pausing does not cancel or rewrite jobs.

## Examples

- `downcroc batch pause bat_123 --reason "review copy"` — pause a batch.
- `downcroc batch pause --all --reason "maintenance"` — pause every existing batch.
- `downcroc batch resume bat_123` — resume a paused batch.
- `downcroc batch resume --all` — resume every paused batch.

## See also

- [approve.md](approve.md) — approve or cancel a batch
- [inspect.md](inspect.md) — see batch state (including paused)
- [reassign.md](reassign.md) — move or delete batch work
- [../09-job/job.md](../09-job/job.md) — pause/resume individual jobs
- [../01-service/service.md](../01-service/service.md) — service-level pause/resume
- [../07-account/account.md](../07-account/account.md) — pause/resume an account
- [../part-i/03-keeping-it-running/stuck.md](../part-i/03-keeping-it-running/stuck.md) — when work is not moving
- [../19-logs/events/service-holds.md](../19-logs/events/service-holds.md) — hold-related log events
- [../19-logs/events/jobs-dispatch.md](../19-logs/events/jobs-dispatch.md) — batch/job pause and dispatch events

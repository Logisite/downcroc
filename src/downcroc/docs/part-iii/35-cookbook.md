---
title: Cookbook
commands: [batch.submit, batch.approve, status, service, vault, batch.show, job.list, job.show, failed, logs, account]
concepts: [batch, job, daemon, vault, failed, queued, hold, approval, account]
---

# Cookbook

Short, task-oriented recipes for common work. Each recipe points at the commands
and chapters that explain the details; for exact flags and behavior, follow the
Part II contract for the command you run.

## Start the daemon and unlock

1. Start in the background: `downcroc service start` (or run attached with
   `downcroc serve`).
2. Check it: `downcroc service status` or `downcroc status`.
3. Unlock credentials: `downcroc vault unlock`.

The [[daemon]] can run while the [[vault]] is locked, but credential-backed work
needs the vault unlocked. A clean stop locks the vault again. See
[Turn it on](../part-i/01-starting/turn-it-on.md) and
[service](../part-ii/01-service/service.md).

## Send a batch

1. Prepare input and review the result (`downcroc prepare ...`).
2. Submit to create a [[batch]]/[[job]]s (`downcroc submit ...`). Depending on
   options, work may start [[queued]] or await [[approval]].
3. If approval is required, review and approve (`downcroc review` /
   `downcroc approve ...`).
4. Watch progress: `downcroc status`, `downcroc batch show <batch>`,
   `downcroc job list --batch <batch>`.

See [Pipeline](30-pipeline.md) and the batch commands in Part II.

## See why work is not moving

1. `downcroc status` for daemon, vault, and sending/queue overview.
2. `downcroc batch show <batch>` and `downcroc job show <job>` for state, holds,
   attempts, and errors.
3. Check for service/account/batch/job pauses or approval waits (a [[queued]] job
   can be held by another layer).
4. `downcroc logs --follow` (or recent logs) to correlate events.

See [Troubleshooting](36-troubleshooting.md) and [States](33-states.md).

## Pause and resume sending

- Pause the whole service: `downcroc service pause [--for DURATION] [--reason ...]`.
  Resume: `downcroc service resume`.
- Pause/resume at other scopes where supported (batch/job/account) to hold only
  that work.

Pausing holds dispatch; it does not cancel or delete work and does not recall
mail already sent/in flight. See [service](../part-ii/01-service/service.md) and
[Safety](34-safety.md).

## Handle failed or retrying jobs

1. List and inspect: `downcroc failed`, `downcroc job show <job>`.
2. Read the state and error: `retry_wait` means it will be tried again at
   `next_attempt_at`; [[failed]] is terminal for that attempt sequence.
3. Fix the underlying cause if needed (account/credentials, content, policy),
   then retry/requeue using the failed/retry commands as appropriate.

See [Failures](32-failures.md) and [failed](../part-ii/10-failed/failed.md).

## Check an account

- `downcroc account list` / `downcroc account show <account>` for status, pause,
  and auth preflight information.
- If an account needs reauth or cannot send, reconnect or resolve credentials and
  confirm it is connected/unpaused.

Account readiness affects whether its jobs can become eligible. See
[account](../part-ii/07-account/account.md) and [States](33-states.md).

## Follow-ups and threads

- Define/inspect follow-ups on the campaign/batch flow and review derived step
  status in `batch show`.
- If a step is skipped, suppressed, deferred, or broken, check the reported
  reason/counts (replies/bounces/suppression, timing, parent not sent, or thread
  issues).
- Approval-required follow-up steps wait for approval before child work
  dispatches.

See [Seats and threads](31-seats-and-threads.md) and [Pipeline](30-pipeline.md).

## Inspect configuration and paths

- Effective config and schema: `downcroc config show`, `downcroc config schema`.
- Resolved paths and overall state: `downcroc status`.

Some config changes require a daemon restart (`downcroc service restart`). See
[Configuration reference](38-config.md). 

## Stop cleanly

- `downcroc service stop` stops the daemon; on a clean shutdown inbound workers
  stop and the vault is locked. Stopping does not delete your data.

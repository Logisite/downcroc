---
title: Troubleshooting
commands: [status, doctor, service, vault, logs, failed, job.show, batch.show, account]
concepts: [daemon, vault, failed, queued, hold, job, batch, account]
---

# Troubleshooting

When something is not behaving as expected, start by finding out *where* the
work is and *why* it is there. Most problems become clear once you separate a
stopped or locked [[daemon]] from a held [[job]], a waiting retry from a [[failed]]
job, and an [[account]] issue from a batch or approval issue.

Use [States](33-states.md) for status meanings, [Pipeline](30-pipeline.md) for
how work moves, and [Failures](32-failures.md) for retry vs terminal outcomes.

## Start with the overall picture

- **`downcroc status`** shows daemon, [[vault]], sending, accounts, and queue at a
  glance. It is the fastest way to see whether the daemon is running, the vault
  is unlocked, or sending is paused.
- **`downcroc service status`** focuses on the managed daemon/service state and
  service-level sending hold (and exits non-zero when the daemon is not running
  healthy).
- **`downcroc doctor`** runs diagnostics that can point at configuration or
  environment issues.

If the daemon is stopped or unreachable, other state-changing work cannot be
processed until it is running again (`downcroc service start` or `downcroc
serve`). A stopped daemon also means no sending is happening.

## The vault is locked

Symptoms: commands or sends that need credentials cannot proceed; status shows the
vault locked.

- Unlock with `downcroc vault unlock`. downcroc starts locked and a clean stop
  locks the vault again, so this is expected after a start/stop cycle.
- Repeated bad passwords trigger throttling; wait for the reported retry delay
  before trying again. The vault never reveals secrets in output.

## Work is not sending

Identify which layer is holding it:

- **Service paused:** `service status`/`status` will show sending paused (possibly
  timed, with reason and held counts). Resume with `downcroc service resume` (or
  wait for a timed pause to expire).
- **Batch, account, or job paused/held:** inspect `batch show`, `job show`, or
  account views and holds. A [[queued]] job can be held by any of these layers.
  Resume the specific hold that applies.
- **Awaiting approval:** a [[batch]] or jobs waiting for [[approval]] do not
  dispatch until approved. See `review`/batch approval commands.
- **Schedule/window/quota/capacity:** work may be waiting for its window,
  `not_before`, daily allowance, or available capacity/binding. These are waits,
  not failures.
- **Account not ready:** `needs_reauth`, disabled/paused, or missing usable
  credentials prevent sending on that path. Check the account’s status and auth
  preflight and reconnect/fix as needed.
- **In flight:** a job in `sending` is mid-attempt; some actions cannot apply
  until the lease/attempt settles.

## Jobs are retrying or failed

- **`retry_wait`:** the last attempt hit a transient/deferrable condition and the
  job will be tried again at `next_attempt_at` (backoff applies). Look at the last
  error, attempts, and logs to understand the cause.
- **`failed`:** the job is terminal for that attempt sequence. Use `downcroc
  failed` and `job show` to inspect the error code/message and attempts, then
  retry according to the command’s behavior if appropriate.
- **`sent_unconfirmed`:** the outcome was uncertain; it is often counted as sent
  but is distinct from a confirmed `sent` and may need attention rather than a
  blind retry.

## Follow-ups did not go out

Follow-up steps are derived and depend on state and signals:

- Check step/declaration status in `batch show` (or follow-up views): steps can be
  scheduled, pending, deferred, skipped, [[suppressed]], cancelled, retired, broken,
  or waiting because the parent was not sent.
- **Skipped/suppressed:** often due to reply, bounce, or stop/suppression rules or
  no eligible candidates. Counts/reasons indicate why.
- **Broken/thread issues:** if the reply chain cannot be built safely, the step is
  reported as broken for that case rather than guessed.
- **Approval:** an approval-required follow-up step waits for approval before its
  child work dispatches.

## Reading logs

`downcroc logs` (and `--follow`) shows structured daemon events: leases, sends,
retries, holds, pauses/resumes, account/auth issues, and follow-up planning
outcomes. When the cause is not obvious from state alone, correlate the job/batch
ids and recent events. Logs and events must not contain credentials; if you need
more detail than is recorded, improve the logging rather than exposing secrets.

## When to change state

- **Resume/pause** controls holds; use the scope that matches the hold
  (service/account/batch/job).
- **Cancel** stops future sends but cannot recall mail already sent or in flight.
- **Delete/reassign/retry** operations have guards and state requirements; read the
  Part II contract and prefer dry-run/preview where available.

If behavior seems inconsistent with these rules, compare the observed state and
recent events against [States](33-states.md) and the relevant command contract in
Part II.

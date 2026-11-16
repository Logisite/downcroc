---
title: Failures
commands: [failed, job.show, batch.show, status, logs]
concepts: [failed, job, batch, account, queued]
---

# Failures

This chapter explains how downcroc represents things that did not go as planned:
what counts as a temporary setback versus a final failure, where those outcomes
surface, and how they relate to retries, holds, and follow-ups.

For the definitive list of status words, see [States](33-states.md). For how a
[[job]] moves through an attempt, see [Pipeline](30-pipeline.md).

## Temporary setbacks and `retry_wait`

Not every problem ends a job. A send attempt can be deferred when the outcome is
transient: a temporary transport/provider condition, a busy or unavailable path
for the moment, or quota/rate pressure that means “try later” rather than “never”.

In those cases the job moves to `retry_wait` (or remains in a retryable path) and
records when it may be tried again (`next_attempt_at`). Retry timing is governed
by backoff: the delay grows from a base by a factor, is capped, and includes
configured jitter so retries do not all fire at once (see
[Configuration reference](38-config.md): `dispatch.retry_*`).

A job in `retry_wait` is not [[failed]]; it is waiting for its next eligible
attempt, subject to holds, windows, quota, and account/transport availability.

## Final failures

A job becomes `failed` when the send does not complete successfully and is not
scheduled to retry — for example a non-retryable error, or a case where retries
are exhausted or not allowed. The job records the last error code/message and the
number of attempts so you can see what happened.

`failed` is a terminal state for that attempt sequence. You can inspect failed
work with `downcroc failed` and `job show`, and retry/requeue it according to the
rules exposed by those commands (retry creates follow-up work as appropriate
rather than silently rewriting history).

## Uncertain sends

Some attempts cannot be fully confirmed. A job may become `sent_unconfirmed` when
delivery was handed off but the outcome is uncertain. This is treated as a sent
outcome in many views/counts but remains distinct from `sent` and may be subject
to reconciliation. It is neither a clean `sent` nor a `failed` job; treat it as a
case that needs awareness rather than automatic re-sending without understanding.

## Blocked work is not always a failed job

Work can stop moving without the job becoming `failed`:

- **Holds and pauses:** service, [[account]], [[batch]], or job-level holds keep
  eligible state from dispatching. The job’s state (often [[queued]] or
  `retry_wait`) can stay the same while a hold explains why it is waiting.
- **Account attention:** an account can be `needs_reauth`, unavailable, paused, or
  otherwise unable to send on the required path. Auth preflight and account
  status surface these conditions; a blocked send path may defer or prevent
  progress until resolved.
- **Approval:** work awaiting [[approval]] is not failing — it is waiting for a
  decision. Rejection/cancellation is a different, explicit outcome.

When diagnosing “nothing is moving”, distinguish between a job that is *failed*,
one that is *waiting to retry*, and one that is *held or ineligible*.

## Sending, accounts, and follow-ups

Failures and blocks appear at different layers:

- **Sending attempts:** produce `retry_wait`, `failed`, or uncertain outcomes on
  jobs, with error details and attempt counts.
- **Accounts and connectivity:** an account that cannot authenticate or provide a
  usable credential (for example needing reconnect/reauth, or temporarily
  unavailable) prevents its work from progressing normally and is reported on the
  account and in send outcomes/logs.
- **Follow-ups:** a follow-up step may be skipped, suppressed, deferred, broken,
  or unable to run for a recipient depending on stop conditions (reply/bounce/
  suppression), timing, missing parent state, or a broken thread chain. Derived
  step status and counts explain these outcomes; a broken thread is recorded as
  such rather than guessed.

## Where failures surface

- **`downcroc failed`** lists failures and retry-related work you can act on.
- **`job show` / `batch show`** show state, attempts, next attempt time (when
  waiting), and last error information.
- **`downcroc status`** and account/batch views show held/blocked contexts and
  counts.
- **`downcroc logs`** records structured events (send attempts, retries, blocked
  reasons, follow-up outcomes) that explain what happened and when.

When in doubt, read the job state together with its error, attempts, any active
holds, and recent log events: together they describe both the outcome and the
reason.

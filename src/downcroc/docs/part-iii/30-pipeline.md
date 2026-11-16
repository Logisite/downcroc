---
title: Pipeline
commands: [batch.submit, batch.approve, batch.show, job.list, status]
concepts: [pipeline, batch, job, queued, failed, hold, approval]
---

# Pipeline

This chapter follows a message from the moment you prepare it to the moment
downcroc considers the work finished. It is the story of how a [[batch]]
becomes [[job]]s, how those jobs become eligible to send, and how results and
follow-ups move through the system.

For the exact status words you will see along the way, see [States](33-states.md).
For how many sends can move at once and how replies stay in the same
conversation, see [Seats and threads](31-seats-and-threads.md).

## From input to a batch

Work starts as input: a prepared campaign (for example from CSV or a template
flow) or another submission path that produces messages and options. Preparing
and submitting build a campaign snapshot and turn it into a [[batch]] with one
[[job]] per recipient message.

At this point downcroc records what is to be sent: recipients, rendered
content/subject, source and routing information, and batch options such as reply
suppression and stop conditions. Jobs are created in a send state that reflects
the chosen path: jobs that require [[approval]] start waiting for approval,
while jobs on an auto-approved path start as [[queued]]. The batch itself starts
in `awaiting_approval` or `sending` accordingly.

A sample/approval flow can exist before the whole batch is released. In that
case the batch remains a unit you can inspect and approve, and its jobs do not
dispatch until released. See the Part II contracts for
[prepare](../part-ii/08-batch/prepare.md), [submit](../part-ii/08-batch/submit.md),
and [approve](../part-ii/08-batch/approve.md).

## Approval and release

Approval is a gate, not a transport step. When a batch or follow-up step
requires approval, its jobs wait (`awaiting_approval`) and are not dispatched.
Approving releases those jobs into `queued` according to the chosen mode; a
cancel/reject path leaves the work `cancelled` rather than sent.

Batch-level [[hold]]s and pauses are separate from approval: a batch can be in a
sending state but still held from moving. [States](33-states.md) describes these
layers.

## Becoming eligible

A queued job is not the same as a job that can go out right now. The dispatcher
repeatedly looks for due work and asks whether each job is allowed to move.

Several layers must line up:

- **[[daemon]] and service state:** the daemon must be running and service-level
  sending must not be paused. A stopped daemon sends nothing; a paused service
  holds dispatch until resumed or until a timed pause expires.
- **Holds:** service, account, batch, and job holds all matter. If any
  applicable hold is active, the job waits even though its state may still be
  `queued` or `retry_wait`. `sending is paused` style blocks mean a hold is in
  the way, not that the job record changed to a different send state.
- **Account readiness:** the sending [[account]] must be connected/usable for the
  chosen path (not paused, not needing reauth in a way that prevents use, and
  with credentials available when required). Account status and auth preflight
  explain why an account needs attention.
- **Schedule and window:** jobs respect timing such as `not_before`/due times and
  the account’s sending window and pacing policy (see
  [Configuration reference](38-config.md) and capacity/selection behavior).
- **Quota and capacity:** daily allowance, in-flight limits, and available
  transport capacity determine whether work can be taken now or must wait.
  Capacity is computed from live policy, holds, quota, and transport state.
- **Routing and transport:** a job’s sender policy (pinned or auto-routed) and
  the available healthy bindings determine which transport can attempt it.

When work is due but cannot move, it remains held by the relevant layer rather
than being lost. [Failures](32-failures.md) covers blocked and deferred cases.

## Dispatch and attempts

When a job is eligible, the dispatcher leases it for an attempt and the job
becomes `sending`. A lease means a worker is actively trying to deliver that
message; while in flight, controls that require the job to be idle (for example
pausing that specific job) cannot apply until the attempt settles.

For each attempt downcroc selects an allowed, healthy send transport for the
account and slot plan, records attempt/transport information, and hands the
prepared message to the transport path (such as SMTP or a provider API binding).
If a transport is busy or unavailable for that moment, the attempt may be
deferred rather than treated as a final message failure.

## Outcomes

How an attempt ends determines the job’s next state:

- **Sent:** delivery was accepted/confirmed. The job becomes `sent` (or
  `sent_unconfirmed` when the outcome is uncertain/unconfirmed), quota/attempt
  accounting is committed as appropriate, and the job is counted as a sent
  outcome in views.
- **Retryable / deferred:** a transient condition (temporary transport or
  provider issue, quota/rate pressure, or a deferrable send outcome) moves the
  job to `retry_wait` with a `next_attempt_at`. The job becomes eligible again
  when that time arrives and other conditions allow. Retry timing uses backoff
  (with configured base/factor/cap and jitter).
- **Needs attention / blocked:** if the mailbox must be reconnected or a path is
  not usable, the job is not completed as sent; it may be held back from
  progress and the account or job can surface a reason (for example
  `needs_reauth`). The exact recorded state depends on the condition.
- **Failed:** a final, non-retryable failure (or retries exhausted/not allowed)
  moves the job to [[failed]]. The error code/message and attempts explain why;
  retrying failed work follows the retry/requeue rules exposed by the CLI/API.

Mail already accepted/in flight cannot be recalled. Cancelling or stopping work
prevents future sends; it does not undo a send that has already happened.

## Follow-ups and threads

Follow-ups are derived work attached to earlier sent messages. Declarations and
step definitions describe when follow-up steps run and what they send; planning
evaluates candidates against stop conditions and suppression (for example
replies, bounces, or other suppression rules), timing, and the parent chain.

When a follow-up step becomes due and eligible, downcroc creates child follow-up
work (a follow-up [[batch]]/jobs) for the step. Those jobs go through the same
approval/queue/dispatch pipeline as other jobs. Follow-up messages are linked to
the conversation they belong to (parent/root references and reply headers) so
they stay in the same thread; if the chain cannot be built safely, the step is
treated as broken for that case rather than guessed.

Derived step status (scheduled, pending, skipped, broken, retired, and so on) is
reported from declaration, timing, and child-batch/job outcomes. See
[States](33-states.md) and [Seats and threads](31-seats-and-threads.md).

## Where to watch it

- `downcroc status` shows the overall picture (daemon, [[vault]], sending, queue).
- `batch show` and `job list/show` show batch and job progress and states.
- `downcroc failed` focuses on failures and retry-related states.
- `downcroc logs` records structured events as work moves (leases, sends,
  retries, holds, follow-up planning). See [logs](../part-ii/19-logs/logs.md).

The pipeline is designed so that state is explicit: a job’s record, its holds,
and recent events together explain where it is and why it is or is not moving.

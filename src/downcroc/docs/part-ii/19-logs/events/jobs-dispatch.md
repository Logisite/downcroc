---
title: Dispatch, job, and batch log events
commands: []
flags: []
concepts: [job, batch]
screens: []
---

# Dispatch, job, and batch log events

Events around the dispatch/send cycle, job leasing and retries, and batch completion. Primary emitters: `src/downcroc/core/dispatch/service.py`, `src/downcroc/core/holds.py` (hold actions on jobs/batches).

## Dispatch cycle

- `job.leased` (**debug**) — a job was claimed/leased for sending to an account.
  - `job`: job id.
  - `account`: account id the job is leased to.

- `dispatch.failed` (**debug**) — one or more sends in a dispatch cycle ended in failure.
  - `count`: number of failed results in the cycle.

- `dispatch.error` (**debug**, **warning**, or **error** depending on case) — an error while dispatching/sending a job or within the cycle. Emitted for domain errors (level chosen by error kind), for per-job exceptions (a job failure must not kill the cycle), and for unexpected cycle errors.
  - Common fields (as applicable): `job`, `account`, `code`, `error` (exception/type name), `detail` (truncated message), `traceback` (truncated). Field set varies by path.

- `dispatch.allowance_spent` (**warning**) — an account had due work but no remaining daily allowance for the day (logged once per account/day while the condition holds).
  - `account`: account id.
  - `day`: the quota day.
  - `limit`: daily allowance limit.
  - `due`: number of due jobs observed.

- `dispatch.idle` (**debug**) — the dispatcher is idle (e.g. held/paused).
  - `reason`: why it is idle (e.g. `paused`).

- `dispatch.spacing` (**debug**) — the dispatcher applied spacing/delay between sends.
  - `delay_ms`: spacing delay in milliseconds.

- `dispatch.send_start` (**debug**, when emitted) — a send attempt is starting for a job/account (see the record for fields such as `job`, `account`, `kinds`).

- `outbound.unlock` (**debug**) — outbound processing checked/unlocked vault access for a job before delivery.
  - `job`: job id.

- `outbound.account` (**debug**) — outbound processing resolved the sending account for a job.
  - `job`: job id.

## Retries and completion

- `job.retry` (**info**) — a job is scheduled for another attempt after a retryable outcome and attempts remain below the limit.
  - `job`: job id.
  - `attempt`: attempt count at the time of scheduling.
  - `in_s`: backoff delay in seconds before the next attempt.
  - `code`: error/retry code.

- `batch.approved` (**info**) — a batch was approved to proceed with sending.
  - `batch`: batch id.
  - `sample`: whether approval was in sample/single mode (as applicable).

- `batch.cancelled` (**info**) — a batch was cancelled.
  - `batch`: batch id.
  - `sent_so_far`: number of jobs already sent.

- `batch.done` (**info**) — a batch in the `sending` state finished with no remaining active jobs (`awaiting_approval`, `queued`, `sending`, `retry_wait`).
  - `batch`: batch id.
  - `sent`: number of sent jobs.
  - `failed`: number of failed jobs.

- `batch.completed` (**published event**) — emitted alongside batch completion.
  - `batch_id`: batch id.
  - `sent`: number of sent jobs.
  - `failed`: number of failed jobs.

- `job.cancelled` (**info**) — a job was cancelled.
  - `job`: job id.
  - `batch`: batch id.

- `job.cancelled` (**info**) — a job was cancelled.
  - `job`: job id.
  - `batch`: batch id.

## Job and batch hold actions

State changes from hold controls emit their own records (primary emitter: `src/downcroc/core/holds.py`):

- `job.paused` (**info**, log; also published) — a job was paused. Key fields: `job`, `batch`, and `reason` (on the published event/where emitted).
- `job.resumed` (**info**, log; also published) — a job was resumed. Key fields: `job`, `batch`, `reason` (as applicable).
- `batch.paused` (**info**, log; also published) — a batch was paused. Key fields: `batch`, `reason`, and held-job counts/impact as emitted.
- `batch.resumed` (**info**, log; also published) — a batch was resumed. Key fields: `batch`, `reason`, held-job counts as emitted.

(See [service-holds.md](service-holds.md) for service/account-level holds and capacity events; see [failures.md](failures.md) for terminal failures and retry-from-failure actions.)

## Batch creation and routing

- `batch.created` (**info**, log; also published) — a batch was created from an input/campaign.
  - `batch`: batch id.
  - `source`: source path (log).
  - `jobs`: number of jobs created.
  - `followups`: number of follow-up steps.
  - Published fields may include `batch_id`, `jobs`, `source_kind`, `state`.

- `batch.reused` (**info**, when emitted) — an existing batch was reused (e.g. retrying a submit with the same key).
  - Batch/id and context fields as emitted.

- `batch.duplicate_warning` (**info/warning**, when emitted) — duplicate recipients/overlap was detected for a batch/input.
  - Fields as emitted (counts/recipients/context).

- `batch.reassigned` (**info**, when emitted) — jobs in a batch were reassigned.
  - Batch/target/count fields as emitted.

- `batch.deleted` (**info**, when emitted) — a batch was deleted.
  - Batch/id and count fields as emitted.

## Job send outcomes and transport results

- `job.send_start` (**debug**, when emitted) — a send attempt is starting.
  - `job`, `account`, and selected transport/kinds as emitted.

- `job.sent` (**info**) — a job was sent successfully (or delivery was confirmed/reconciled).
  - `job`, `account`, `batch`/message identifiers and provider/transport details as emitted.

- `job.sent_unconfirmed` (**info/warning**, when emitted) — a send completed but could not be fully confirmed.
  - `job`, `account`, `code`/reason and context as emitted.

- `job.reconciled` (**info**, when emitted) — an uncertain send was reconciled against provider state (e.g. Sent folder).
  - `job`, `account`, outcome/state as emitted.

- `job.deleted` (**info**, log; also published) — a job was deleted.
  - `job` and `batch`/`id` as emitted.

- `job.blocked` (**info/warning**, when emitted) — a job could not proceed due to a blocking condition.
  - `job`, `account`, `code`/`reason` as emitted.

- `smtp.accepted` (**info**) — the SMTP transport accepted a message for delivery.
  - `account`, `job`, `binding`/transport identifiers and server response details as emitted.

- `smtp.rejected` (**warning/error**) — the SMTP transport rejected a message.
  - `account`, `job`, `code`/reason and server/transport detail as emitted.

- `smtp.uncertain` (**warning**, when emitted) — the SMTP outcome is uncertain (delivery could not be confirmed).
  - `account`, `job`, reason/detail as emitted.

- `smtp.session_open` (**debug/info**, when emitted) — an SMTP session was opened.
  - `account`/binding and connection details as emitted.

- `smtp.session_closed` (**debug/info**, when emitted) — an SMTP session was closed.
  - `account`/binding and reason/duration as emitted.

- `smtp.session_reused` (**debug**, when emitted) — an existing SMTP session was reused.
  - `account`/binding as emitted.

- `smtp.session_dropped` (**debug/warning**, when emitted) — a pooled SMTP session was dropped.
  - `account`/binding and reason as emitted.

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [failures.md](failures.md) — job failures and retry/forget/reconcile
- [../../09-job/job.md](../../09-job/job.md) — inspect jobs
- [../../08-batch/inspect.md](../../08-batch/inspect.md) — inspect batches
- [../../part-iii/30-pipeline.md](../../part-iii/30-pipeline.md) — how work moves through the system
- [../../part-iii/33-states.md](../../part-iii/33-states.md) — job and batch states

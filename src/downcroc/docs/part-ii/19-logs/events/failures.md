---
title: Failure log events
commands: []
flags: []
concepts: [failed, job, batch]
screens: []
---

# Failure log events

Events for jobs that fail and for actions taken on failed jobs (retry, forget, reconcile, purge). Primary emitters: `src/downcroc/core/dispatch/failures.py`, `src/downcroc/core/dispatch/service.py` (retry scheduling/failure transitions).

- `job.failed` (**warning**, log; also published) — a job reached a failed state and was recorded as a failure. Emitted when the failure is recorded (once per recorded failure).
  - `job`: job id.
  - `account`: attribution account id (who the job was sent/attributed to, when known).
  - `code`: failure/error code.
  - `detail`: failure message (truncated).
  - `attempts`: number of attempts made.
  - Published payload also includes identifiers such as `id`, `batch`, `account`, `code`, `message`.

- `failure.retried` (**info**) — a previously failed job was reset for retry via the failure service.
  - `job`: job id.
  - `attempt`: the attempt count recorded on the failure.

- `job.retried` (**published event**) — emitted when a failed job is retried.
  - Includes identifiers such as `id`/job and `batch`.

- `failure.forgotten` (**info**) — a failed job was removed from the failure set (forgotten) without retrying it.
  - `job`: job id.
  - `batch`: batch id.

- `failure.reconciled` (**info**) — failed-job records were reconciled (for example, restoring records from the failure log into the failure store where appropriate).
  - `count`: number of records reconciled.

- `failures.purged` (**info**) — failed-job records were purged according to criteria.
  - `count`: number removed.
  - `states`: states filter used (if any).
  - `older_than_days`: age filter used (if any).

Related dispatch behavior: when retries are exhausted or a job is marked failed through the dispatch path, it is recorded via the failure service (emitting `job.failed`); when a retryable outcome is rescheduled, `job.retry` is emitted (see [jobs-dispatch.md](jobs-dispatch.md)).

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../10-failed/failed.md](../../10-failed/failed.md) — inspect and act on failed jobs
- [../../09-job/job.md](../../09-job/job.md) — inspect a job
- [jobs-dispatch.md](jobs-dispatch.md) — dispatch and retry scheduling
- [../../part-iii/32-failures.md](../../part-iii/32-failures.md) — failure concepts
- [../../part-iii/33-states.md](../../part-iii/33-states.md) — job states

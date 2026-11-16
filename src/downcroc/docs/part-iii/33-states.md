---
title: States
commands: [status, service, vault, account, batch.list, batch.show, job.list, job.show, review, failed]
concepts: [job, batch, queued, sent, failed, daemon, vault, account, hold, approval, suppressed, needs-reauth]
---

# States

This page is the reference for the status words downcroc uses. It describes
what each state means, the conditions that usually produce it, and where you see
it.

A single unit of work can be affected by more than one layer at once. For
example, a [[job]] can be in `queued` state while it is not currently moving
because its [[batch]] is paused, its [[account]] is paused, the service-level
send pause is active, the batch is still awaiting [[approval]], or the job
itself is paused. State words describe the record; the reason it is waiting may
come from a different layer.

## Jobs

A [[job]] is one message to one recipient. Job state is the core send state.

| State | Meaning | Typical path / notes | Where you see it |
| --- | --- | --- | --- |
| `queued` | The job is waiting to be sent. | Initial state for normal/manual jobs and for jobs released after [[approval]]. A queued job may still be held by a pause, [[hold]], policy, quota, schedule (`not_before`), or an ineligible account. | `job list`, `job show`, `batch show`, `failed` selection, logs/events |
| `awaiting_approval` | The job is waiting on batch approval. | Used when a [[batch]] or follow-up step requires approval before dispatch (for example review-mode campaign submits or approval-required follow-up steps). On approval, jobs move to `queued`; on cancel/reject paths they can become `cancelled`. Jobs in this state are not dispatched. | `job list/show`, `batch show`, review flows |
| `sending` | A worker holds a lease and is actively attempting delivery. | A queued/retryable job becomes `sending` while SMTP/API send work is in progress. On success it becomes `sent` or `sent_unconfirmed`; on a transient failure it becomes `retry_wait`; on a final failure it becomes `failed`. A crash can leave a row `sending` until lease/reconciliation handling resolves it. | `job list/show`, `batch show`, logs |
| `sent` | Delivery was accepted/confirmed by the send path. | Terminal success state. Counted as sent work. | `job list/show`, batch/job counts, `status`, `stats` |
| `sent_unconfirmed` | The send was attempted but the outcome could not be fully confirmed. | Produced for uncertain/unconfirmed send outcomes (for example when delivery acceptance cannot be confirmed). Treated as a sent outcome for counting/reporting in many views, but it remains distinct from `sent` and may be subject to reconciliation. | `job list/show`, batch/job counts, `stats`, logs/events |
| `retry_wait` | A transient failure occurred; the job is waiting for its next attempt. | Set when a send can be retried (for example temporary SMTP/provider conditions or quota/rate-limit exhaustion). `next_attempt_at` controls when it becomes eligible again. It can move to `sending` on the next attempt, or to `failed` when retries are exhausted/not allowed. | `job list/show`, `failed`/retry views, `--state retry_wait` filters |
| `failed` | The send did not complete successfully and is not currently scheduled to retry. | Terminal failure for that attempt sequence. Inspect the error code/message and attempts; retry creates follow-up work according to retry rules. | `job list/show`, `batch show`, `downcroc failed` |
| `cancelled` | The job will not be sent. | Terminal stopped state. Can result from batch/job cancellation, rejected approval, or follow-up stop conditions that cancel pending follow-up work. Mail already in flight cannot be recalled. | `job list/show`, batch/job counts |

**Related job fields (not separate states):**

- **Paused job:** a job may have `paused_at` / `paused_reason`. A paused job is
  held at job level and is not dispatched while paused. A job that is currently
  `sending` cannot be paused in that moment.
- **Sender policy:** jobs are `pinned` to an account or `auto`-routed at send
  time. This affects routing, not the job state word.
- **Lease/error fields:** `attempts`, `next_attempt_at`, `lease_*`,
  `last_error_*`, and `retryable` explain progress within/beyond the states
  above.

## Batches

A [[batch]] groups jobs submitted together (a campaign send or a follow-up
step). Batches are also the unit for [[approval]] and batch-level holds.

| State | Meaning | Typical path / notes | Where you see it |
| --- | --- | --- | --- |
| `awaiting_approval` | The batch is waiting for approval. | Submitted batches that require review start here (or return here while a sample/approval flow is pending). Approving releases jobs according to the chosen mode; cancelling/rejecting leaves the batch `cancelled`. | `batch list --state awaiting_approval`, `batch show`, `review` |
| `sending` | The batch is active. | Jobs may be queued, sending, retrying, or otherwise in progress. A batch can be in `sending` while dispatch is held by pauses/holds/policy. | `batch list/show`, `status`, `review` context |
| `done` | The batch has no remaining active send work. | Terminal completion state for the batch. A `done` batch may include jobs that ended `sent`/`sent_unconfirmed` and, depending on outcomes, jobs that ended `failed` or `cancelled`; check counts and job states for the result. | `batch list/show` |
| `cancelled` | The batch was cancelled/stopped and is not an active sending batch. | Terminal stopped state. Jobs that were not sent may be cancelled; work already in flight cannot be recalled. | `batch list/show` |

**Batch kinds:** `campaign` (top-level send) and `follow_up` (derived from a
parent batch/step).

**Related batch fields:** a batch can be paused (`paused_at` / `paused_reason`),
shown as paused/held in views even while its state remains
`awaiting_approval` or `sending`. Batches also carry approval mode, options,
warnings, and suppression/count information.

## Accounts

An [[account]] state (`status`) describes the mailbox/account record and whether
it is ready to use.

| Status | Meaning | Typical path / notes | Where you see it |
| --- | --- | --- | --- |
| `pending` | The account exists but is not yet connected/verified. | Common after adding an account before successful connect/auth verification. | `account list/show`, `status` (needs attention) |
| `unverified` | The account has not been verified as ready. | Treat as needing setup/verification before relying on it for sending. | `account list/show` |
| `connected` | The account is connected and usable. | Healthy/ready state for normal operation, subject to policy, quota, pauses, and [[vault]] availability. | `account list/show`, `status` |
| `needs_reauth` | Stored credentials/auth are no longer valid; the account must be reconnected. | Set when authentication fails in a way that requires user action (for example reconnect/re-authorize). Sending that depends on it will be affected until fixed. | `account list/show`, `status`, doctor, logs |
| `disabled` | The account is disabled. | Not used for normal sending until enabled/replaced as applicable. | `account list/show` |

**Related account fields:**

- **Paused account:** `paused_at` / `paused_reason` mean sends from that
  account are held at account level (separate from `status`).
- **Auth preflight:** accounts/vault views may include `auth_checked_at`,
  `auth_status`, `auth_error`, and `auth_action`. Known reported auth status
  values include `ok`, `needs_reauth`, and `unavailable`, with actions such as
  `reconnect`, `retry`, or `unlock` when applicable. These explain the latest
  check/result and may align with account `status` (for example `needs_reauth`),
  but are reported as preflight/check fields rather than as the account status enum.
- **Credential presence:** vault/account views can report whether a credential
  is present, but only when the [[vault]] state allows that check.

## Vault

The [[vault]] holds credentials. Its state controls whether protected operations
can access secrets.

| State | Meaning | Typical path / notes | Where you see it |
| --- | --- | --- | --- |
| `locked` | The vault is closed; secrets are not available in memory. | The [[daemon]] starts locked. A clean stop locks the vault. Some operations (status, inspection of non-secret data) still work while locked. | `status`, `vault status`, `doctor`, API |
| `unlocked` | The vault is open for this daemon run; secrets can be used. | Set by `vault init`/`vault unlock` (unlock is idempotent when already unlocked). Required for sending/fetching/credential use as applicable. | `status`, `vault status`, API, logs (`vault.unlocked`/`vault.locked`) |

Vault status also reports attempts/throttle information (for example attempts
left and retry delay) when relevant.

## Daemon and service

These words describe the local background service/process, as reported by
`downcroc status` and `downcroc service status`.

| State | Meaning | Typical path / notes | Where you see it |
| --- | --- | --- | --- |
| `running` | The daemon process is alive and responding. | Healthy service state. `status` may additionally show `uptime_s` and URL/pid. | `downcroc status`, `downcroc service status` |
| `stopped` | No running daemon/service is recorded as active. | Normal when the service is not started. Start with `downcroc service start` (or `serve`). | `downcroc status`, `downcroc service status` |
| `stale` | A recorded process/lock entry exists but the process is gone. | Usually follows a crash/unclean exit. The next start/cleanup can recover by replacing stale state. | `downcroc status`, `downcroc service status`, logs |
| `unreachable` | The recorded process exists but does not answer health checks. | The process may be stuck or not serving the expected API. Check recent logs. | `downcroc status`, `downcroc service status`, `auth status` |

**Service-level sending:** separate from daemon liveness, sending dispatch can be
`running` or **paused** (`sending_paused_*` runtime state). A service pause
holds dispatch without changing policy values. Status surfaces whether sending is
paused, since/until/reason (when present), and held job/batch counts.

## Follow-up steps and declarations

Follow-ups are tracked per parent batch/step. There are two related kinds of
state: declaration state (the stored follow-up definition) and derived step
status (what that step is doing now).

### Follow-up declaration states

| State | Meaning |
| --- | --- |
| `active` | The declaration is in effect and can produce/schedule work according to its rules. |
| `removing` | The declaration is being retired/removed; pending behavior is winding down. |
| `retired` | The declaration is no longer active. |

### Derived follow-up step status

`batch show` / follow-up status views derive a step status from the
declaration, parent/child batch state, timing, and per-recipient outcomes.
Common values:

| Status | Meaning |
| --- | --- |
| `scheduled` | Not due yet (or waiting for its scheduled time/window). |
| `pending` | Due now with eligible candidates, but child work has not completed yet. |
| `deferred` | Temporarily deferred for this step/parent in the current status context. |
| `awaiting_approval` | A child batch/step exists and is waiting for approval. |
| `sending` | Child work is in progress (pending active jobs). |
| `done` | Step work completed successfully. |
| `partial` | Some work sent, but some failed or was cancelled. |
| `skipped` | Nothing to send for this step (for example no eligible candidates or all were blocked/ineligible). |
| `cancelled_child` | The child [[batch]] for the step was cancelled. |
| `retired` | The declaration/step is retired (including removing declarations with no active child work). |
| `broken` | The step cannot run as defined (for example missing/invalid payload) and no child batch represents completed work. |
| `parent_not_sent` | The parent [[batch]] has not sent the work this step depends on. |

Step status views also report counts such as candidates, not due, replied,
bounced, [[suppressed]], pending, sent, failed, cancelled, and awaiting (reflecting
evaluated outcomes and any child-batch job states).

## Other relevant states

### Paused / held layers

“Held” is not a single enum; it means dispatch is prevented by some layer. Common
layers are: service-level sending pause, account pause, batch pause, and job
pause (each with `paused_at`/reason where applicable). A job can also be
effectively waiting because it is `awaiting_approval`, `queued` behind schedule,
`retry_wait`, or blocked by policy/quota/connectivity.

### Suppressed

A recipient/follow-up can be [[suppressed]] (for example due to a reply, bounce,
or stop/suppression rules). Suppressed recipients are recorded and not sent.
Common recorded reasons include reply- or bounce-driven suppression and other
suppression/stop conditions; suppression previews/counts show the address,
account, and reason where available.

### Connect attempts

Account connection attempts (for example OAuth) use internal attempt states:
`pending`, `succeeded`, `failed`, `cancelled`, and `expired`. These are usually
surfaced through connection flows and errors rather than as job/batch states.

## See also

- [../part-ii/02-status/status.md](../part-ii/02-status/status.md) — system status view
- [../part-ii/09-job/job.md](../part-ii/09-job/job.md) — job commands
- [../part-ii/08-batch/inspect.md](../part-ii/08-batch/inspect.md) — batch inspection
- [../part-ii/08-batch/holds.md](../part-ii/08-batch/holds.md) — pausing/holding work
- [../part-ii/10-failed/failed.md](../part-ii/10-failed/failed.md) — failed jobs
- [../part-ii/13-review/review.md](../part-ii/13-review/review.md) — approval flow
- [37-glossary.md](37-glossary.md) — term definitions


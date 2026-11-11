# 06 - Send pipeline

## Shape of the work

```
file  ->  parse  ->  validate  ->  snapshot  ->  render every message  ->  jobs
                                                                          |
                                                              awaiting_approval
                                                                          |
                                                        dry run: 1 sample, then all
                                                                          |
                                                              queued, per account
                                                                          |
                                                          dispatcher: window, allowance,
                                                          jitter, lease, send, record
```

Every step before `queued` is synchronous and atomic from the caller's point of view. Once jobs
exist, the client may disconnect and the work continues.

## Current build

Until intake and dispatch exist, a one-off job is created through `POST /api/jobs` and sent
through `POST /api/jobs/{id}/send`. That path builds the MIME message, mints the Message-ID, and
runs the same SMTP send and Sent-folder reconciliation described here. It is a pre-dispatch seam,
not a second scheduler; normal batches will use the dispatcher. Manual creation and sending share
the batch transport selection and reject archived, paused, or disconnected senders.

Batch, job, and pending estimates carry `as_of` and `basis`. They are computed on every read from
live policy, quota, holds, and transport state, so a policy or config change is visible on the
next request without a background refresh.

## Follow-up declarations

A campaign file can declare automatic follow-ups in its immutable snapshot. A batch can also gain a
retroactive declaration after submission. A declaration is a `batch_followup_declarations` row,
never an edit to `source.json`.

Two kinds exist:

- `shared`: one body with per-recipient overrides.
- `payload`: one message per parent recipient, stored in the content store.

The planner merges snapshot steps and active declarations by step key. Child jobs are threaded to
the parent message that actually reached the recipient. The child is pinned to the account that
sent the parent. Remove works before a child exists. Retire keeps child history. Every declaration
update carries a version, and a stale version is rejected.

## SMTP seats

The SMTP seat is a transport reservation, not an account status. At most `dispatch.smtp_seats`
connections are open. A sticky seat is held until a cap, failure, or batch drain, then the next
account in randomized round-robin order takes it. Pinned jobs bind the account, not the
transport: an unseated API-capable account sends through the Gmail API.

## Provider response classification

Every reserved send attempt ends with a terminal outcome and a `finished_at` timestamp. A failure
before the transport attempt is finalized against `pending`, a reauth failure blocks the job with
`retryable=false`, and startup reconciliation closes stale reservations as `interrupted`.

The provider response is the source of truth. SMTP classification reads the enhanced status code
and the response text, not the numeric reply alone. A daily limit or rate limit marks the binding
`quota_exhausted` and leaves the job in `retry_wait`; an unknown recipient fails the job; a policy
or reputation block fails the job and cools the binding; authentication marks the account
`needs_reauth`. Gmail classification reads the error reason and both the `Retry-After` header and
the JSON message. A provider retry time wins over the configured minimum cooldown, and the
original provider text is stored on the attempt and in the failed queue.

## Inputs

You draft elsewhere. downcroc takes a file path, reads it once, and never reads it again.

Two formats with two different jobs:

| Format | Carries | Rendering |
|---|---|---|
| JSON | ready messages | none, the content is sent as written |
| CSV | recipient rows | one template renders a message per row |

Detection is by content, not extension. A JSON document with `schema`, `campaign`, or `messages`,
or a bare array of message objects, is a campaign. A first line that parses as a delimited header
is CSV.

### JSON campaign

A bare array is the minimal file, one message per recipient:

```json
[
  {
    "to": { "email": "ana@example.com", "name": "Ana" },
    "subject": "One question about Northwind",
    "text": "Hi Ana, ...",
    "html": "<p>Hi Ana, ...</p>"
  }
]
```

The wrapped form adds campaign policy and a follow-up sequence:

```json
{
  "schema": "downcroc.campaign/v1",
  "producer": { "tool": "my-writer", "version": "2.1", "generated_at": "2026-10-23T08:00:00Z" },
  "campaign": {
    "key": "october-outreach",
    "name": "October outreach",
    "routing": { "mode": "auto", "exclude": ["acct_9"] },
    "options": {
      "suppress_replies": true,
      "reply_window_days": 60,
      "not_before": "2026-10-24T09:00:00Z",
      "stop_on": ["reply", "bounce"],
      "allow_duplicates": false
    }
  },
  "messages": [
    {
      "key": "ana-step1",
      "to": { "email": "ana@example.com", "name": "Ana" },
      "subject": "One question about Northwind",
      "text": "Hi Ana, ...",
      "html": "<p>Hi Ana, ...</p>",
      "reply_to": null,
      "attachments": ["deck.pdf"],
      "followups": {
        "bump-1": { "subject": "Re: One question about Northwind", "text": "Hi Ana, one more thought ..." },
        "bump-2": { "skip": true }
      }
    }
  ],
  "followups": [
    {
      "key": "bump-1",
      "after_days": 4,
      "when": "no_reply",
      "subject": "Re: One question about Northwind",
      "text": "Hi again, ...",
      "require_approval": false
    }
  ]
}
```

`to.email`, `subject`, and one of `text` or `html` are required per message. `email` is the only
required key inside `to`. Unknown keys inside a message are rejected, because there is no template
namespace to absorb a typo. Keys prefixed `x-` are stored and ignored, so a producer can carry its
own metadata.

The producer never writes `From`, `Date`, `Message-ID`, `In-Reply-To`, `References`, MIME
boundaries, `Content-ID`, `Bcc`, arbitrary headers, or an account per message. If an export
contains them, the daemon strips them, reports the ignored fields, and sends the derived version.

`producer` is stored for audit and never used for sending. `campaign.key` is the producer's stable
identifier, stored for reconciliation. `messages[].key` is unique within the file and is the
matching key for follow-ups, overrides, and export reports.

Attachments are relative to the JSON file's directory. Absolute paths and `..` are refused. The
daemon reads each file once at submit, checks its size against the provider cap, and snapshots it.
`reply_to` is the only header a producer may set.

A duplicate address inside one campaign is an error, with both message keys named, unless
`allow_duplicates` is true. A second message to the same person then starts its own thread.

### Follow-up steps in JSON

Follow-up content lives at campaign level, so one file describes the whole sequence. A message may
override any step by key, or opt out of it with `skip: true`. An override key that does not match a
declared step is an error, and a step declared twice is an error. Resolution order is per-message
override, then campaign step.

`after_days` counts from the previous step that actually sent for that recipient, in the account's
local timezone. `when` is `no_reply` or `always`, both still subject to suppression. `subject`
defaults to `Re: <previous subject>`. `require_approval` defaults to false and makes the derived
batch wait for a human.

### CSV

Header row required. `email` is the required column; a `name` column is recognised and mapped
automatically. Every other column becomes a template variable. A template must be supplied,
because a CSV carries no message.

| Concern | Handling |
|---|---|
| Encoding | UTF-8, BOM tolerated |
| Delimiter | comma, with `;` and tab auto-detected when the header row has no commas |
| Quoting | standard RFC 4180, multi-line values allowed |
| Duplicate headers | rejected, because the resulting ambiguity is silent |
| Row count sanity | a file that changes size between hash and parse is rejected |
| Duplicate address | collapsed, reported as a count |
| Empty rows | skipped |

Merge tags are written `{{ Column Name }}`, matched case-insensitively and tolerant of spaces
around the name. The daemon exposes what a client needs to make this usable without reading
documentation: detected columns, per-row validation with a stable row reference, render preview
for any row, test send to an arbitrary address, row-level exclusion before submit, and per-row
status after sending. Missing variables block the submit with row and column named. No blank
substitution, ever.

### Templates

Templates apply to CSV batches and to follow-up steps that name one. A JSON message carries its
own content and never renders a template.

A template is a directory in `~/.config/downcroc/templates/<name>/`:

| File | Purpose |
|---|---|
| `template.toml` | subject, optional defaults, optional attachments, optional reply-to |
| `body.txt` | plain text body |
| `body.html` | optional HTML body, inlined for email at send time |
| `assets/` | images and files, referenced from `body.html` by `cid:` name, or attached by filename |

Bodies are files rather than blobs inside TOML so they diff cleanly and the TUI can edit them as
text. The TUI never writes a template field it did not read.

Variables:

| Kind | Examples |
|---|---|
| Built-in | `{{ email }}`, `{{ name }}`, `{{ account_email }}`, `{{ batch_name }}`, `{{ date }}` |
| Supplied | anything in the recipient object or CSV columns |
| Defaults | declared in `template.toml`, used when the input omits the key |

Rendering is strict. An unknown or missing variable is a validation error at submit time, never
a blank space in a sent email. Defaults are the only way to make a variable optional, and they
are explicit.

## Validation

Runs before anything is written to the content store. A batch either passes completely or is
rejected with a report pointing at the row or message that failed.

| Check | Failure |
|---|---|
| Address syntax | `invalid_address` with message key or row |
| Duplicate address, case-insensitive | CSV collapses and reports, JSON rejects unless allowed |
| Required message content | `missing_subject`, `empty_subject`, `missing_content` |
| Template renders for every row | `missing_variable`, naming the key and the row |
| Follow-up override matches a declared step | `unknown_step`, naming the message and the step |
| Attachments exist, stay inside the source directory, fit the provider cap | `attachment_missing`, `attachment_path`, `attachment_too_large` |
| Suppressed recipient, when enabled | skipped with `suppressed`, listed in the preview |
| Account exists and is connected, or one is eligible for auto routing | `account_unavailable` |
| Every job has a unique Message-ID | internally guaranteed, checked as an invariant |
| Schema version known | `unsupported_schema` |
| Unknown key inside a message or step | `unknown_field`, unless prefixed `x-` |

Failed rows and messages are not silently dropped. The response lists them with a code, the
message key or row, and the field. Submitting a batch with zero valid messages is an error, not an
empty batch.

## Snapshot

At submit:

1. normalize the source to the internal campaign representation, including schema version,
   producer metadata, and follow-up steps
2. copy that to `content/batches/<bat_id>/source.json` and record its `sha256` on the batch row
3. resolve routing once and record the account on each job
4. render or copy every message and store `content/jobs/<job_id>/message.eml`
5. mint each job's `Message-ID`

The original file is now irrelevant. Editing it changes nothing. The hash is the proof of what
was submitted. The snapshot is the input; the jobs table is the routing and send record.

## Dry run

The point is to see the mail in your own inbox before six hundred people do.

```
submit -> batch.awaiting_approval, all jobs queued but locked
        |
        +-> 5 random samples rendered exactly as they will be sent
        |
        approve(one) -> that job is released and sends immediately,
        |               bypassing the window, jitter and bucket (it is one message)
        |               batch stays awaiting_approval, sample_job_id recorded
        |
        you check the real inbox in Gmail
        |
        approve(all) -> remaining jobs enter the bucket at the next tick
```

Rules:

- `campaign.options.approval` is `review` by default and `auto` to skip the gate. Auto batches go
  straight to `queued`; the review response is still returned for the client to show.
- The sample is byte-identical to the real message except for the `Date` header. If a send-time
  header changed meaningfully, the dry run would be theatre.
- `approve(one)` cannot be repeated. The sample job is recorded, and a second call is rejected
  with `sample_already_sent`.
- `approve(all)` before any sample is allowed but emits a warning in the TUI. It is the
  deliberate "I do not need a test send" path.
- Jobs in `awaiting_approval` are not visible to the dispatcher and do not consume allowance.
- The samples are chosen at random from the valid jobs, and the chosen ids are recorded so the
  TUI can show which were sent. A JSON message can also be previewed by key.

## Account binding

Every job is bound to one account **at creation**. That account owns the From address, the
conversation, and the quota.

- Explicit binding: `routing.mode` is `fixed` and the campaign names the account.
- Auto binding: each message is assigned at creation by remaining daily allowance among connected,
  enabled, non-excluded accounts, computed once with a seed from `campaign.key` so a resubmission
  produces the same spread.
- Moving: a job may be reassigned while it is `queued`. Reassignment re-renders the From header
  and message body reference. It is refused once a lease is held, because the message may already
  be on the wire.
- Follow-ups inherit the parent job's account. Always. A thread must stay in one mailbox or the
  reply attribution falls apart.
- The batch detail exposes recipient, account, job id, message id, state, and last error, so the
  "which message went from which mailbox" record is always answerable.

## Dispatch

```
loop:
  wait for a job event or 2 seconds
  for each account in random order, weighted by remaining allowance:
      if account is connected, enabled, inside its window, has allowance:
          pick the oldest due job bound to that account
          take a lease, send, record, release
```

Details:

| Concern | Behaviour |
|---|---|
| Order | bucket drain: oldest due first. No spreading across the day |
| Account choice | weighted random by remaining daily allowance, so a 200/day account carries more than a 40/day one |
| Job choice within an account | oldest `next_attempt_at`, then oldest `created_at` |
| Concurrency | one in-flight send per account by default, configurable. A global in-flight cap bounds open sockets; it is concurrency, not a rate |
| Jitter | uniform random delay in `[min, max]` between consecutive sends on the same account |
| Window | local-time start and end, per account, wrapping past midnight when start > end |
| Outside the window | jobs wait, nothing fails |
| Allowance exhausted | account sleeps until its next local midnight |
| Batch cancelled mid-flight | queued jobs become `cancelled`; the in-flight one completes normally |

No scheduling feature. There is no "send at 09:00" promise. The only time control is the
window plus the daily bucket, and downcroc is explicit about that rather than pretending
otherwise.

`not_before` exists on a batch as a floor, not a schedule: a job will not be considered before
that timestamp, and after it the bucket decides. It has no UI in the first client.

## Quota

Per account, from config:

| Setting | Meaning |
|---|---|
| `daily_allowance` | the cap: successful sends per local day |
| `window_start`, `window_end` | local hours during which sending is allowed |
| `jitter_min`, `jitter_max` | seconds between sends on that account |
| `max_in_flight` | concurrent sends on that account |
| `enabled` | account participates in dispatch |

**The daily allowance is the only quota in the system.** There is no hourly cap, no global ceiling,
and no burst guard. An account with a 200/day allowance and a wide window will drain 200 as fast
as jitter and `max_in_flight` allow, and that is the intended behaviour.

Hourly numbers are recorded so you can see the shape of a day, not so the dispatcher can enforce
anything against them. If a day is going out in an unusual burst, the Stats screen shows it; it
does not block it. The controls you actually have are the daily allowance, the window, the jitter
range, and disabling an account.

The allowance counts **attempts that reached the wire**, not successes, so a retry storm cannot
exceed the number a provider sees. Counters live in `quota_buckets` and survive restart.

There is no provider-side cross-check. These are your numbers, chosen by you. The daemon does not
try to guess Gmail's limits, and it does not silently lower your setting.

## Crash reconciliation

The job row is the only send-state store. `sending` is committed before SMTP is contacted. On
unlock, every `sending` row is checked against the Sent folder by its minted Message-ID.

| Result | Action |
|---|---|
| Found | mark `sent`, publish `job.sent`, log `job.reconciled` with `found=true` |
| Not found after the configured searches | return to `queued`; the dispatcher sends it once more |
| Search unavailable | leave `sending`, log `outbound.reconcile_failed`, retry on the next unlock |

This closes both crash windows. A crash after the server accepted but before the commit finds the
message in Sent and sends nothing new. A crash before acceptance finds nothing, releases the row,
and sends exactly once. The number of Sent-folder searches and the delay between them are
configured by `reconcile_attempts` and `reconcile_delay_s`.

## Outbound settings

| Setting | Meaning |
|---|---|
| `smtp_timeout_s` | connect, authentication, and DATA timeout for one send |
| `lease_seconds` | how long a worker owns a `sending` row |
| `reconcile_attempts` | Sent-folder searches before deciding a message never left |
| `reconcile_delay_s` | delay between those searches |

## Dispatch settings

| Setting | Meaning |
|---|---|
| `tick_s` | loop interval when no send is running |
| `max_attempts` | total attempts before a transient failure becomes terminal |
| `retry_base_s` | first retry delay |
| `retry_factor` | multiplier applied per attempt |
| `retry_cap_s` | ceiling on the computed retry delay |
| `retry_jitter` | fraction applied either side of the retry delay |
| `global_in_flight` | cap on concurrent sends across all accounts |
| `shutdown_join_s` | time allowed for in-flight sends during shutdown |

The dispatcher claims up to `global_in_flight` jobs per tick, respecting each account's
`max_in_flight`. It waits for that wave to finish, applies the per-account jitter delay, and
ticks again. A lease is held for `outbound.lease_seconds`; an expired lease is claimable.

## Follow-up settings

| Setting | Meaning |
|---|---|
| `check_s` | interval between scans for due follow-up steps |
| `sync_timeout_s` | bound on the forced inbound sync before deriving a step |
| `defer_s` | how long an account waits after a failed sync before the next attempt |

A failed sync logs `followup.sync_failed` with `defer_s` and defers the step instead of mailing.

## Retries

| Property | Value |
|---|---|
| Attempts | 5 total, configurable |
| Backoff | exponential, base 30s, factor 2, cap 1 hour |
| Jitter | plus or minus 20 percent, so retries do not synchronise |
| Scope | transient failures only |
| Attempt counter | incremented when the job is claimed; an interrupted attempt is still counted |

Classification:

| Condition | Class | Result |
|---|---|---|
| DNS failure, connection refused, TCP reset | transient | retry |
| Timeout during connect or after DATA | transient | retry |
| 421, 450, 451, 452 | transient | retry |
| 550, 551, 552, 553, 554 | permanent | `failed` |
| other 5xx | transient | retry |
| 530, 534, 535 | auth | account to `needs_reauth`, job back to `queued` |
| Render error, missing attachment | permanent | `failed` |

The five-attempt ceiling, exponential backoff, and jitter are dispatcher work. The current send
path records `retry_wait` with an immediate next attempt and leaves the ceiling to the dispatcher.

A failed job never blocks its batch. The batch completes with a failure count.

## Failures

Terminal failures are written in two places, in this order:

1. append to `failed.jsonl` in the data directory
2. insert into `failed_queue`

The file is the durable, portable record. The table is the query surface the TUI reads. A startup
reconciliation compares them and reinserts a row whose append succeeded but whose insert did not,
but only while the job is still `failed`. Retrying rewrites the file atomically without that job
and deletes its row, so a restart cannot resurrect a cleared failure.

The TUI shows a persistent count in the status bar and a screen listing failures with recipient,
account, reason code, and the human reason. Actions are: retry one, retry all, dump to a file.

Retrying resets `attempts` to zero and returns the job to `queued`, keeping the original
`Message-ID` if the message never left, and minting a new one if it did. That distinction matters:
reusing a Message-ID that reached the recipient would make their client merge two different
messages.

## Suppression

Default on, per batch, and switchable.

> A recipient is suppressed from a batch on account X when a **confirmed reply** from that address
> exists in a thread rooted in any earlier job sent from account X.

Why per account and not global: two accounts may legitimately write to the same person, and
suppressing across them would silently drop mail you asked for.

Suppression is computed at submit, shown in a preview, and recorded on each job as a reason. It is
recomputed once at approval time so a reply that arrived during the dry run is honoured. After
sending starts, suppression does not retroactively cancel jobs.

For follow-ups, suppression defaults to on and is the entire point: the default recipient set is
"the original recipients who have not replied".

## Follow-ups

A follow-up is a first-class batch, not a special job type, and it is derived from the parent
batch. Recipient eligibility, account, and thread always come from the parent, never from the
follow-up file.

### Sequence model

Steps are declared with the campaign, so one JSON file describes the whole sequence. A derived
batch is created when a step becomes due, for each parent recipient who is still eligible:

- no confirmed reply, no bounce, no suppression
- campaign not cancelled, and the parent step actually sent
- account inherited from the parent job
- thread anchored to the previous outbound step for that recipient

`after_days` counts from the previous step that sent, in the account's local timezone. If the
daemon was off when a step came due, it sends at the next opportunity, not never.

Before deriving due steps for an account, the daemon forces an inbound sync for that account with
a bounded timeout. If the sync fails, the step is deferred rather than mailed. Sending to someone
who replied during the downtime is the failure that matters.

Derivation is idempotent: one job per `(parent_job_id, step_key)`, enforced by a unique index, so
a restart cannot duplicate a step. A step whose parent never sent is skipped with a reason.

`campaign.options.stop_on` defaults to `["reply", "bounce"]` and cancels every remaining step for
that recipient, not only the next one. `require_approval` on a step produces an
`awaiting_approval` derived batch and uses the sample flow; otherwise the step runs when due.

### Content sources

A follow-up payload can be ready messages or CSV plus template, matched to parent recipients by
`messages[].key` first and address second. The parent batch decides who is eligible. Extras are
reported, gaps for eligible recipients are errors. This is what allows a JSON campaign followed by
a CSV follow-up, or the reverse.

### Threading headers

| Header | Value |
|---|---|
| `Message-ID` | newly minted, unique to this job |
| `In-Reply-To` | the previous outbound step's `Message-ID` |
| `References` | the chain of previous outbound ids in this thread |

If the previous step failed, the anchor is the most recent step that actually sent. Reusing the
parent's `Message-ID` would break attribution and confuse every mail client involved.

Attribution still works because each message's own `Message-ID` is the anchor: a reply to the
follow-up carries `In-Reply-To: <follow-up id>`, which maps to the follow-up job, whose thread maps
to the batch and to the parent batch.

## Message-ID minting

Format: `<{utc-timestamp}.{random}@{sender-domain}>`, for example
`<20261022T091500Z.9f3c1a@example.com>`.

Rules:

- the domain is the account's domain, not a downcroc domain, so the id looks native
- uniqueness is enforced by a unique index; a collision re-mints
- the id is stored on the job before any bytes are sent, so reconciliation can find it later
- the id is never reused across a retry that reached the wire

## MIME construction

| Field | Source |
|---|---|
| `From` | account address with the account label as display name |
| `To` | the single recipient, with name when known |
| `Subject` | rendered, header-encoded when needed |
| `Date` | send time, UTC, RFC 5322 |
| `Message-ID` | minted at creation |
| `Reply-To` | reserved; not set by the current send path |
| `MIME-Version` | `1.0` |
| Body | `multipart/alternative` when HTML is present, `text/plain` alone otherwise |
| Attachments | files referenced by the template, `multipart/mixed`, base64, size checked before send |
| Inline images | `multipart/related` with `Content-ID` references rewritten from `cid:` in the HTML |
| HTML inlining | CSS is inlined at render time, from the template, and the original HTML is retained |

One recipient per message, always. No shared `To`, no `Bcc`, no list headers. A batch of 600 is
600 messages, each of which can fail, retry, and be replied to on its own.

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

## Inputs

You draft elsewhere. downcroc takes a file path, reads it once, and never reads it again.

### JSON

Two accepted shapes. A bare array is the simple case:

```
[
  { "email": "ana@example.com", "name": "Ana", "company": "Northwind" },
  { "email": "bo@example.com",  "name": "Bo",  "company": "Contoso"  }
]
```

A wrapped object carries batch metadata:

```
{
  "name": "october-outreach",
  "template": "intro",
  "account": "acct_7f2a",            // or null for auto-selection
  "options": { "suppress_replies": true, "reply_window_days": 60 },
  "recipients": [ { "email": "...", "name": "..." } ]
}
```

`email` is the only required key. Everything else is available to the template. Nested values
are supported and flattened for template use (`company.name` -> `{{ company.name }}`).

### CSV

Header row required. `email` is the required column; a `name` column is recognised and mapped
automatically. Every other column becomes a variable. A template must be supplied, because a CSV
carries no message.

| Concern | Handling |
|---|---|
| Encoding | UTF-8, BOM tolerated |
| Delimiter | comma, with `;` and tab auto-detected when the header row has no commas |
| Quoting | standard RFC 4180, multi-line values allowed |
| Duplicate headers | rejected, because the resulting ambiguity is silent |
| Row count sanity | a file that changes size between hash and parse is rejected |

### Templates

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
rejected with a per-row report.

| Check | Failure |
|---|---|
| Address syntax | `invalid_address` on that row |
| Duplicate address, case-insensitive | collapsed, reported as a count |
| Suppressed recipient, when enabled | skipped with `suppressed`, listed in the preview |
| Template renders for every row | `missing_variable`, naming the key and the row |
| Attachments exist and fit the provider cap | `attachment_too_large` |
| Account exists and is connected | `account_unavailable` |
| Every job has a unique Message-ID | internally guaranteed, checked as an invariant |
| Subject non-empty after render | `empty_subject` |

Rows that fail are not silently dropped. The response lists them, and the TUI shows them as a
table before you approve. Submitting a batch with zero valid rows is an error, not an empty batch.

## Snapshot

At submit:

1. copy the source file to `content/batches/<bat_id>/source.json`, normalized to the internal
   representation
2. record `sha256` of that snapshot on the batch row
3. render every message once and store `content/jobs/<job_id>/message.eml`
4. mint each job's `Message-ID`

The original file is now irrelevant. Editing it changes nothing. The hash is the proof of what
was submitted.

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

- The sample is byte-identical to the real message except for the `Date` header. If a send-time
  header changed meaningfully, the dry run would be theatre.
- `approve(one)` cannot be repeated. The sample job is recorded, and a second call is rejected
  with `sample_already_sent`.
- `approve(all)` before any sample is allowed but emits a warning in the TUI. It is the
  deliberate "I do not need a test send" path.
- Jobs in `awaiting_approval` are not visible to the dispatcher and do not consume allowance.
- The samples are chosen at random from the valid jobs, and the chosen ids are recorded so the
  TUI can show which were sent.

## Account binding

Every job is bound to one account **at creation**. That account owns the From address, the
conversation, and the quota.

- Explicit binding: the batch names an account.
- Auto binding: each recipient is assigned at creation, by the same weighted-random rule the
  dispatcher uses, computed once so the result is stable.
- Moving: a job may be reassigned while it is `queued`. Reassignment re-renders the From header
  and message body reference. It is refused once a lease is held, because the message may already
  be on the wire.
- Follow-ups inherit the parent job's account. Always. A thread must stay in one mailbox or the
  reply attribution falls apart.

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

## Retries

| Property | Value |
|---|---|
| Attempts | 5 total, configurable |
| Backoff | exponential, base 30s, factor 2, cap 1 hour |
| Jitter | plus or minus 20 percent, so retries do not synchronise |
| Scope | transient failures only |
| Attempt counter | incremented when the attempt reached the wire |

Classification:

| Condition | Class | Result |
|---|---|---|
| DNS failure, connection refused, TCP reset | transient | retry |
| Timeout during connect or after DATA | transient | retry |
| 421, 450, 451, 452 | transient | retry |
| 5xx from the server | transient | retry, unless it repeats identically five times |
| 535, 534 | auth | account to `needs_reauth`, job back to `queued` |
| 550, 551, 553, invalid recipient | permanent | `failed` |
| 552, message too large | permanent | `failed` |
| 554, policy rejection | permanent | `failed` |
| Render error, missing attachment | permanent | `failed` |

A failed job never blocks its batch. The batch completes with a failure count.

## Failures

Terminal failures are written in two places, in this order:

1. append to `failed.jsonl` in the data directory
2. insert into `failed_queue`

The file is the durable, portable record. The table is the query surface the TUI reads. A startup
reconciliation compares them and reinserts a row whose append succeeded but whose insert did not.

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

A follow-up is a first-class batch, not a special job type.

| Field | Value |
|---|---|
| `kind` | `follow_up` |
| `parent_batch_id` | the batch being followed up |
| Template | new message, usually shorter |
| Recipients | original recipients minus confirmed repliers |
| Account | inherited per job from the parent job |
| Thread | linked to the parent thread |

Threading headers for a follow-up:

| Header | Value |
|---|---|
| `Message-ID` | newly minted, unique to this job |
| `References` | parent job's `Message-ID` |
| `In-Reply-To` | omitted |

This puts the message in the same conversation in the recipient's client while remaining a
distinct message that generates its own reply chain. Reusing the parent's `Message-ID` would
break attribution and confuse every mail client involved.

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
| `From` | account address with the configured display name |
| `To` | the single recipient, with name when known |
| `Subject` | rendered, header-encoded when needed |
| `Date` | send time, UTC, RFC 5322 |
| `Message-ID` | minted at creation |
| `Reply-To` | config, per account, optional |
| `MIME-Version` | `1.0` |
| Body | `multipart/alternative` when HTML is present, `text/plain` alone otherwise |
| Attachments | files referenced by the template, `multipart/mixed`, base64, size checked before send |
| Inline images | `multipart/related` with `Content-ID` references rewritten from `cid:` in the HTML |
| HTML inlining | CSS is inlined at render time, from the template, and the original HTML is retained |

One recipient per message, always. No shared `To`, no `Bcc`, no list headers. A batch of 600 is
600 messages, each of which can fail, retry, and be replied to on its own.

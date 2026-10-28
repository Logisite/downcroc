# 07 - A file becomes jobs

**What to build:** submit a JSON campaign of ready messages or a CSV plus template and get a
batch. JSON carries content, recipients, and campaign policy; the daemon strips producer-supplied
mechanics, validates every message, resolves routing across accounts, snapshots the source, mints
Message-IDs, and creates jobs bound to accounts. CSV carries rows only and renders one template.
Five rendered samples come back for review: approving one sends it immediately, approving all
queues the rest, cancelling stops the batch. Follow-up steps are parsed, validated, and stored,
but no follow-up job is created here.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] a 1,000-message JSON campaign imports, and a 1,000-row CSV imports, through the same endpoint
- [ ] a bare array of messages and a wrapped `downcroc.campaign/v1` campaign both import
- [ ] an unknown schema version is refused with `unsupported_schema`, nothing written
- [ ] producer-supplied `From`, `Date`, `Message-ID`, `In-Reply-To`, `References`, and headers are
      stripped and reported as ignored
- [ ] unknown keys inside a message are rejected unless prefixed `x-`
- [ ] a bad message or row is reported with its message key or row number and the field
- [ ] duplicate recipients: CSV collapses and reports, JSON rejects naming both message keys
      unless `allow_duplicates` is true
- [ ] a variable used in a CSV template but missing in a row is a validation error with row and
      column
- [ ] an attachment with an absolute path or `..` is refused, and a missing file is named
- [ ] the snapshot hash is recorded and the normalized source is stored
- [ ] routing is resolved once and recorded per job, and a resubmission with the same campaign key
      produces the same assignment spread
- [ ] fixed routing pins one account, auto routing spreads across eligible accounts
- [ ] five samples render without sending, and any message or row previews by key or row
- [ ] approving one sends exactly one and leaves the rest queued
- [ ] approving all queues the remainder, and auto approval skips the review gate
- [ ] follow-up steps and per-message overrides validate, and no follow-up job exists yet
- [ ] cancelling a batch leaves nothing queued and reports what was already sent

**Logs:** the events this ticket introduces. Validation failures are one aggregate line at info and
one detail line per rejected row or message at warning, so a 1,000 message file does not flood the
file.

- `input.detected` path, format, schema
- `input.parsed` messages, duplicates, duration_ms
- `input.field_ignored` key, message
- `validation.failed` count, first_key, first_field
- `validation.row_rejected` key, row, field, code
- `routing.resolved` batch, accounts, messages
- `template.rendered` name, duration_ms
- `snapshot.stored` hash, bytes
- `batch.created` batch, jobs, followups
- `batch.approved` batch, sample
- `batch.cancelled` batch, sent_so_far

**Commit:** `feat(intake): add campaign parsing, routing, batch submit`

---
title: batch inspect
commands: [batch.list, batch.show, batch.suppression]
flags: [--state, --limit, --offset, --all, batch.list --parents, batch.list --sort, batch.show batch_id, batch.suppression batch_id]
concepts: [batch, follow_up_step]
screens: []
---

# batch inspect

`batch inspect` covers the commands for looking at submitted batches: listing batches, showing a batch and its recipients, and viewing [[suppressed]] recipients. These commands read state; they do not change it.

## Usage

```text
downcroc batch list [--state STATE] [--limit LIMIT] [--offset OFFSET] [--parents] [--sort {recent,stale}]
downcroc batch show <batch_id> [--all]
downcroc batch suppression <batch_id>
```

## Commands

### list

Lists batches.

```text
downcroc batch list [--state STATE] [--limit LIMIT] [--offset OFFSET]
downcroc batch list --parents [--sort {recent,stale}]
```

- `--state` filters by batch state: `awaiting_approval`, `sending`, `done`, `cancelled`.
- `--limit` sets maximum rows (1–500, default 100). `--offset` skips rows for paging.
- `--parents` shows parent batches only, folding follow-up child batches into each parent row with a follow-up summary: declared steps, last follow-up step and when it happened (relative time, e.g. `fu1 · 4d`), pending/waiting follow-up work, and last activity.
- `--sort {recent,stale}` controls ordering for `--parents` (default `recent`). `stale` puts the oldest-touched/most neglected parents first so batches that need follow-up attention rise to the top.

**Output**

- Default: prints a table of batches (id, name, kind, state — marked paused when applicable, approval, sent count, replies, eta, created time) and a page footer when paged. If no batches match, it reports that and suggests validating an input; if batches are awaiting approval, it suggests `downcroc review`.
- With `--parents`: prints a parent-focused table (batch, name, sent, replies, steps, last follow-up, pending, last activity) with relative times. With `--json`, each row may include a `followups` summary (`steps`, `last`, `pending`, `last_activity`).
- With `--json`: prints the batch list (and summaries when `--parents`) as JSON.

### show

Shows a batch and its recipients.

```text
downcroc batch show <batch_id> [--all]
```

- Displays batch details: id, name, kind, state (including paused), approval, routing, source/template references, timestamps, counts, eta/capacity information when available, options (such as reply suppression/window, `not_before`, stop conditions), warnings/ignored fields, and recipients.
- By default recipients are shown as a sample (with a note to use `--all` if more exist). With `--all`, shows every recipient (including source key/row context where available).

**Output**

- Default: a human-readable summary, counts, options/warnings, and a recipients table.
- With `--json`: the batch (including details and recipients/counts) as JSON.

### suppression

Shows [[suppressed]] recipients for a batch.

```text
downcroc batch suppression <batch_id>
```

- Lists recipients that are suppressed for the batch (for example due to replies/bounces/stop conditions or suppression rules), showing address, account, and reason.
- If there are no suppressed recipients, it reports that.

**Output**

- Default: a table of suppressed recipients, or “no suppressed recipients”.
- With `--json`: the suppression list as JSON.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch list` — list batches.
- `downcroc batch list --state awaiting_approval` — list batches waiting for approval.
- `downcroc batch show bat_123` — show a batch and a sample of recipients.
- `downcroc batch show bat_123 --all` — show every recipient.
- `downcroc batch suppression bat_123` — list suppressed recipients for a batch.

## See also

- [prepare.md](prepare.md) — validate and preview input before submitting
- [submit.md](submit.md) — submit a batch
- [approve.md](approve.md) — approve or cancel a batch
- [holds.md](holds.md) — pause and resume batches
- [reassign.md](reassign.md) — reassign or delete a batch
- [followups.md](followups.md) — declare and inspect follow-up steps
- [due.md](due.md) — cross-batch follow-up outlook
- [thread.md](thread.md) — visualize a batch's follow-up thread and replies
- [../09-job/job.md](../09-job/job.md) — inspect individual jobs
- [../13-review/review.md](../13-review/review.md) — review batches awaiting approval
- [../part-i/03-keeping-it-running/stuck.md](../part-i/03-keeping-it-running/stuck.md) — when work is not moving
- [../part-iii/33-states.md](../part-iii/33-states.md) — batch and job states

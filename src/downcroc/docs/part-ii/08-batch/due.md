---
title: followups due
commands: [followups, followups.due]
flags: [followups.due --due]
concepts: [follow_up, follow_up_step, batch]
screens: []
---

# followups due

`followups due` gives a cross-batch view of follow-up work that needs attention:
which [[batch]]es and [[follow_up_step]]s are due now or coming up, so you can
decide what to act on without scanning batches one by one.

## Usage

```text
downcroc followups due [--due {today,7d,Nd,all}]
```

## What it shows

For each relevant follow-up step across parent batches, the outlook lists the
batch, step, rule (`when` and `after_days`), when it is due, and counts:

- **due**: `due now` for steps ready to act on (or awaiting/sending), or a
  relative time such as `in 2d` / `overdue 1d` for upcoming/overdue scheduled
  steps.
- **counts**: a compact summary of ready/due, awaiting, waiting/not-due, and
  replied/sent recipients as applicable.

Results are ordered by urgency (actionable/due items first).

## Options

- `--due {today,7d,Nd,all}` (default `today`): the time window.
  - `today`: steps due now (actionable) and those due/overdue today.
  - `7d` or `Nd` (for example `14d`): include steps due within the next N days.
  - `all`: include all upcoming/relevant follow-up steps.

## Output

- Default: a table (batch, name, step, rule, due, counts) with relative times.
- With `--json`: the outlook as JSON (items with batch/step/state/rule/counts and
  due timing fields, using ISO timestamps).

## Examples

- `downcroc followups due` — what needs attention today.
- `downcroc followups due --due 7d` — outlook for the next 7 days.
- `downcroc followups due --due all --json` — full outlook as JSON.

## See also

- [inspect.md](inspect.md) — parent batch list with follow-up summaries
- [followups.md](followups.md) — declare and manage follow-up steps per batch
- [thread.md](thread.md) — visualize one batch's follow-up thread and replies
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md) — how follow-ups run

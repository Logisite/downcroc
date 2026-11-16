---
title: batch thread
commands: [batch.thread]
flags: [batch.thread batch_id, batch.thread --recipient, batch.thread --all]
concepts: [batch, follow_up_step, thread]
screens: []
---

# batch thread

`batch thread` visualizes a [[batch]] and its follow-up conversation: the batch
summary, each follow-up [[follow_up_step]] with its state/counts and timing, and
the reply threads that came back. It helps you see what happened across the
batch and drill into a specific person's chain.

## Usage

```text
downcroc batch thread <batch_id> [--recipient ADDRESS] [--all]
```

## What it shows

- **Batch summary:** id, name, state, sent/reply counts, and when it was created.
- **Follow-ups:** each step with its rule (`when` and `after_days`), state,
  timing (due now / due in / overdue, shown as relative time), child batch (if
  any), and counts (sent, replied, waiting/due, awaiting, etc.).
- **Replies/threads:** threads associated with the batch, showing subject,
  reply/bounce status, and when last seen. By default a subset is shown; use
  `--all` to show every thread.
- **Recipient chain (`--recipient ADDRESS`):** the full per-recipient chain for
  that address: the initial send and each follow-up job in order (step, state,
  when, subject, message id), followed by inbound replies/messages in that thread
  rendered as message cards (from/to/date, reply state, body, attachments).

## Options

- `batch_id` (required): the batch to visualize.
- `--recipient ADDRESS`: focus on one recipient's full send/follow-up/reply chain.
- `--all`: show every reply thread (not just a summary subset).

## Output

- Default: a human-readable tree/summary with relative times (`s/m/h/d/mo`).
- With `--json`: the thread view payload as JSON (batch, steps, threads, and
  `recipient` chain when requested) with ISO timestamps.

## Examples

- `downcroc batch thread bat_123` — show steps and a reply summary for the batch.
- `downcroc batch thread bat_123 --all` — include every reply thread.
- `downcroc batch thread bat_123 --recipient person@example.com` — show that
  recipient's full chain and replies.
- `downcroc batch thread bat_123 --json` — machine-readable thread view.

## See also

- [inspect.md](inspect.md) — list and show batches (including parent follow-up summaries)
- [followups.md](followups.md) — declare and inspect follow-up steps
- [../15-mail/mail.md](../15-mail/mail.md) — read stored mail and threads
- [../part-iii/31-seats-and-threads.md](../part-iii/31-seats-and-threads.md) — seats and threading
- [../part-iii/33-states.md](../part-iii/33-states.md) — states

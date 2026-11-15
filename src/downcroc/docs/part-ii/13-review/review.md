---
title: review
commands: [review]
flags: [--batch]
concepts: [batch]
screens: []
---

# review

`review` lets you see and act on [[batch]]es that are awaiting approval. It is the interactive counterpart to `downcroc batch approve`: list what is waiting, inspect a batch, and choose to send a sample, approve the rest, or cancel.

## Usage

```text
downcroc review [--batch BATCH_ID]
```

- With `--batch BATCH_ID`, opens that batch for review.
- Without `--batch`, shows batches awaiting approval and lets you pick one (interactively) or lists them.

## Behavior

### Selecting a batch

- **No `--batch`, interactive:** lists pending batches to choose from (showing name and how many messages are waiting). If nothing is waiting, it reports that and suggests `downcroc send`.
- **No `--batch`, non-interactive/JSON:** lists pending batches (table or JSON) without prompting.
- **With `--batch`:** loads that batch. In JSON mode it prints the batch; in non-interactive mode it prints the batch details; in interactive mode it opens the action flow for that batch.

### Reviewing a batch

For the selected batch, `review` shows its details: id and name, state and approval, creation time, source, counts (waiting, sent, failed), sample messages (recipient, subject, and a short preview of the text), and any warnings or ignored fields.

If the batch is not in a state that can be approved (`awaiting_approval`), it reports the current state and that approval is not available.

When the batch is awaiting approval and the session is interactive, you are asked what to do next:
- **Send one sample now** — approves mode `one` (leaves the rest held). Confirms before sending.
- **Approve the remaining and send** — approves mode `all`, releasing every waiting message. Confirms before sending (stating how many will be released).
- **Cancel the batch** — cancels the batch (does not recall mail already in flight). Confirms before cancelling.

On approval it reports what was approved and the result; on cancel it reports the batch as cancelled and reminds you that mail already in flight cannot be recalled. Cancelling out of a confirmation raises a cancelled error.

## Output

- Default: lists pending batches or shows batch details and the chosen action/result.
- With `--json`: prints the pending batch list, or the selected batch, as JSON (non-interactive selection paths).

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc review` — review batches awaiting approval interactively.
- `downcroc review --batch bat_123` — review a specific batch.

## See also

- [../08-batch/approve.md](../08-batch/approve.md) — approve or cancel a batch by command
- [../08-batch/inspect.md](../08-batch/inspect.md) — list and show batches
- [../08-batch/submit.md](../08-batch/submit.md) — submit a batch (including holding for review)
- [../12-send/send.md](../12-send/send.md) — guided send flow
- [../part-i/02-first-mail/approve-and-send.md](../part-i/02-first-mail/approve-and-send.md) — approving and sending

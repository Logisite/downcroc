---
title: batch approve and cancel
commands: [batch.approve, batch.cancel]
flags: [--mode, batch.approve batch_id, batch.cancel batch_id]
concepts: [batch]
screens: []
---

# batch approve and cancel

When a [[batch]] is submitted for review, it waits for [[approval]] until you decide what to send. `batch approve` releases it (as a sample or in full). `batch cancel` stops a batch from continuing.

## Usage

```text
downcroc batch approve <batch_id> [--mode {one,all}] [--yes]
downcroc batch cancel <batch_id> [--yes]
```

## Commands

### approve

Approves a batch so it can send.

```text
downcroc batch approve <batch_id> [--mode {one,all}] [--yes]
```

- Approves the specified batch with the chosen mode:
  - `one` sends a sample.
  - `all` sends the rest/all messages (as applicable to the batch’s approval flow).
- Before approving, downcroc shows/identifies the batch and asks for confirmation (including the batch name and mode) unless `--yes` is given or confirmation is satisfied per `--no-input` rules.
- The batch must be in a state that can be approved; the resulting state is reported after approval.

**Output**

- Default: reports the approved batch id (with mode) and its resulting state.
- With `--json`: prints the updated batch as JSON.

### cancel

Cancels a batch.

```text
downcroc batch cancel <batch_id> [--yes]
```

- Cancels the specified batch so it does not continue sending. If the batch is already `cancelled` or `done`, the command reports that it is already in that state and exits with a non-zero status.
- Asks for confirmation unless `--yes` is given or confirmation is satisfied per `--no-input` rules.
- Cancelling prevents further sending/dispatch for the batch as applicable, but **mail already in flight cannot be recalled**.

**Output**

- Default: reports the cancelled batch id and state, and notes that mail already in flight cannot be recalled.
- With `--json`: prints the updated batch as JSON.

## Options

`--mode {one,all}`
: Approval mode for `batch approve`. `one` sends a sample; `all` sends the rest/all.

`--yes`
: Skip the confirmation prompt (where confirmation applies).

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch approve bat_123 --mode one` — approve and send a sample.
- `downcroc batch approve bat_123 --mode all --yes` — approve and send all without prompting.
- `downcroc batch cancel bat_123` — cancel a batch after confirmation.

## See also

- [submit.md](submit.md) — submit a batch (including `--approve`)
- [inspect.md](inspect.md) — inspect batch state and recipients
- [holds.md](holds.md) — pause and resume a batch without cancelling
- [../13-review/review.md](../13-review/review.md) — review batches awaiting approval
- [../part-i/02-first-mail/approve-and-send.md](../part-i/02-first-mail/approve-and-send.md) — approving and sending
- [../part-iii/33-states.md](../part-iii/33-states.md) — batch states

---
title: batch submit
commands: [batch.submit]
flags: [--template, --account, --approve, --key, --dry-run, --allow-overlap, batch.submit path]
concepts: [batch]
screens: []
---

# batch submit

`batch submit` turns a [[campaign]] input file (JSON or CSV) into a [[batch]] that downcroc can send. It validates/previews the input, creates (or reuses) the batch, and can leave it awaiting approval or approve it immediately depending on the options you choose.

Submitting is the step that moves from “a file on disk” to tracked jobs in the system. Use `batch validate`/`batch preview` first when you want to check the input without writing anything.

## Usage

```text
downcroc batch submit <path> [--template NAME|PATH] [--account ID]
                   [--approve {none,one,all}] [--key KEY]
                   [--dry-run] [--allow-overlap]
```

- `path` is a campaign file or CSV.
- `--template NAME|PATH` supplies the template for a CSV input.
- `--account ID` pins every message to the given account.

## How submission works

**Preview and overlap**

Before creating a batch (unless `--dry-run` short-circuits), downcroc previews the input. If the preview reports that some recipients already appear in recent batches (overlap), submission asks for confirmation before proceeding unless you pass `--allow-overlap`. Overlap is a warning to help you avoid contacting the same recipients again unintentionally.

**Dry run**

With `--dry-run`, downcroc validates/previews the input and shows the preview but writes nothing — no batch is created. The result is reported as a dry run.

**Creating or reusing a batch**

On a real submit, downcroc creates the batch from the input (and optional `--key` to submit a single message by key/row; a retry with the same key reuses the batch as applicable). The resulting batch has a state and approval mode (for example awaiting approval or sending), and submission reports whether it was newly submitted or reused.

**Approval at submit time**

`--approve` controls what happens after the batch is created (when it is in a state that can be approved):
- `none` (default behavior) leaves the batch held for review (awaiting approval).
- `one` approves/sends a sample (as supported by approval mode).
- `all` approves and sends the batch.

If the batch is already in a state that cannot be approved in that way, submission reports its current state.

## Output

- Default: reports the submitted/reused batch id and name, its state and approval, and shows capacity/eta information when available. If not quiet, it suggests a next step — `downcroc batch approve <id> --mode all` when the batch is awaiting approval, or `downcroc batch show <id>` otherwise.
- With `--json`: prints the batch (or dry-run/preview result) as JSON.

## Options

`--template NAME|PATH`
: Template name or directory for a CSV input.

`--account ID`
: Pin every message to this account.

`--approve {none,one,all}`
: `none` holds for review, `one` sends a sample, `all` sends. Applied when the created batch is awaiting approval.

`--key KEY`
: Submit one message by key or row; a retry can reuse the batch.

`--dry-run`
: Validate and preview without writing a batch.

`--allow-overlap`
: Submit even when recipients appear in recent batches (skips the overlap confirmation prompt).

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch submit campaign.json` — submit a campaign and leave it awaiting approval.
- `downcroc batch submit campaign.json --approve all` — submit and approve all messages to send.
- `downcroc batch submit campaign.json --approve one` — submit and send a sample.
- `downcroc batch submit campaign.json --account acct_123` — submit with every message pinned to an account.
- `downcroc batch submit campaign.json --key m1` — submit a single message by key.
- `downcroc batch submit campaign.json --dry-run` — preview without creating a batch.
- `downcroc batch submit campaign.json --allow-overlap` — submit despite recent recipient overlap.

## See also

- [prepare.md](prepare.md) — validate, preview, schema, and examples
- [inspect.md](inspect.md) — list and show batches and recipients
- [approve.md](approve.md) — approve or cancel a submitted batch
- [holds.md](holds.md) — pause and resume batches
- [followups.md](followups.md) — add and manage follow-up steps
- [../part-i/02-first-mail/make-a-campaign.md](../part-i/02-first-mail/make-a-campaign.md) — creating a campaign
- [../part-i/02-first-mail/read-the-preview.md](../part-i/02-first-mail/read-the-preview.md) — reading the preview before sending
- [../part-i/03-keeping-it-running/stuck.md](../part-i/03-keeping-it-running/stuck.md) — when work is not moving

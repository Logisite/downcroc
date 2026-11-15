---
title: send
commands: [send]
flags: [--template, --account, --approve]
concepts: [batch]
screens: []
---

# send

`downcroc send` is the guided way to send mail. It can work from an existing [[campaign]] file (JSON or CSV) or, when run interactively without a file, help you compose a one-off message into a reusable draft. It validates and previews the input, asks for the key choices (account, approval), and then submits the batch.

For file-based input it follows the same core flow as `batch validate`/`batch preview`/`batch submit`, but in a single interactive command.

## Usage

```text
downcroc send [path] [--template NAME|PATH] [--account ID] [--approve {none,all}]
```

- `path` is a campaign file (JSON or CSV). If omitted, `send` can compose a message interactively (on a terminal) and write it as a draft campaign.
- `--template NAME|PATH` supplies the template for a CSV input.
- `--account ID` pins every message to the given account.
- `--approve {none,all}` controls whether the batch is held for review or sent once due (see below).

## How it works

### Choosing the source

- **With a file path:** uses that campaign/CSV. For a CSV input, if no `--template` is given and the session is interactive, you are prompted to choose (or create) a template.
- **Without a path (interactive):** you are asked what to send — a campaign JSON file, a CSV plus a template, or a one-off message composed here. For file choices you provide the path (and template for CSV). For compose, see below.
- **Without a path (non-interactive):** the command requires a campaign file and fails with a usage error.

### Composing a one-off message

When you choose to compose (interactive, no file), `send` prompts for recipient (`To`), optional name, subject, and opens an editor for the body. Lines starting with `#` in the editor are removed when the draft is saved. You can add attachment file paths one by one (they are copied into the draft’s `assets/`).

The draft is written as a reusable campaign JSON under the data drafts directory (in a dated folder named from the subject). `send` reports the draft path and suggests editing and re-running `downcroc send <draft>`. Composing creates the draft; to submit it, run `send` again with that draft file.

### Validation and preview

For a file-based send, the input is validated. If it is invalid and the session is interactive, you are shown the validation result and can open the file in `$EDITOR` to fix it, then it is revalidated. A valid input is previewed (showing messages, routing, follow-ups, overlap/capacity information as applicable).

If the preview reports recipient overlap with recent batches, `send` asks for confirmation before continuing.

### Account and approval

- **Account:** if `--account` is not given and the session is interactive, you can choose which connected account sends (or `Auto` to use campaign routing). At least one connected account is required when choosing interactively.
- **Approval:** `--approve none` holds everything for review (default). `--approve all` sends as soon as messages are due (without a second look). In an interactive session without `--approve all`, you are asked to choose between holding for review and sending as soon as due.

### Submitting

After confirmation of the choices, `send` submits the batch from the input (applying the selected approval mode and any overlap allowance). It reports the resulting batch id, name, state, and approval, and shows capacity/eta information when available. When not quiet it suggests the next step (for example `downcroc batch show <id>` or approving a batch held for review).

## Output

- Default: shows validation/preview as needed, then prints the submission result (batch, state, approval) and a suggested next step.
- With `--json`: prints the machine-readable result.

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc send` — interactively choose or compose what to send (terminal only).
- `downcroc send campaign.json` — validate, preview, and submit a campaign file.
- `downcroc send recipients.csv --template intro` — send a CSV using a template.
- `downcroc send campaign.json --approve all` — submit and send as soon as due.
- `downcroc send campaign.json --account acct_123` — pin every message to an account.

## See also

- [../08-batch/prepare.md](../08-batch/prepare.md) — validate, preview, schema, and examples
- [../08-batch/submit.md](../08-batch/submit.md) — submit an input file as a batch
- [../08-batch/approve.md](../08-batch/approve.md) — approve or cancel a submitted batch
- [../13-review/review.md](../13-review/review.md) — review batches awaiting approval
- [../14-template/template.md](../14-template/template.md) — manage templates for CSV sends
- [../part-i/02-first-mail/make-a-campaign.md](../part-i/02-first-mail/make-a-campaign.md) — creating a campaign
- [../part-i/02-first-mail/approve-and-send.md](../part-i/02-first-mail/approve-and-send.md) — approving and sending

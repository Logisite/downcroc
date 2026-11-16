---
title: batch prepare
commands: [batch, batch.validate, batch.schema, batch.example, batch.preview]
flags: [batch.validate path, batch.preview path, batch.preview --account, batch.submit --account, batch.validate --account, batch.pause --all, batch.preview --all, batch.resume --all, batch.show --all, batch.preview --key, batch.submit --key, batch.example --kind, batch.followups.declare --kind, batch.preview --table, batch.followup --template, batch.preview --template, batch.submit --template, batch.validate --template, batch.example --write]
concepts: [batch]
screens: []
---

# batch prepare

Before you submit a [[batch]], you can check that your [[campaign]] input is valid, understand the expected format, generate starter files, and preview how messages will look and where they will go. These commands work on campaign input files (JSON or CSV) and do not create or change a batch in the system, except that `validate` may consult the daemon to report recipient overlap.

## Usage

```text
downcroc batch validate <path> [--template NAME|PATH] [--account ID]
downcroc batch schema
downcroc batch example [--kind {json,followups,csv,template}] [--write DIR]
downcroc batch preview <path> [--template NAME|PATH] [--account ID] [--key KEY] [--all] [--table]
```

## Commands

### validate

Checks an input file offline and reports whether it is ready to submit.

```text
downcroc batch validate <path> [--template NAME|PATH] [--account ID]
```

- `path` is a campaign file or CSV.
- `--template NAME|PATH` names or points to the template for a CSV input.
- `--account ID` pins every message to the given account for validation/routing context.

`validate` parses and checks the input (format, required fields, campaign/message/follow-up structure, routing, duplicates/overlap signals as applicable). If the input is valid, it also attempts to fetch a preview from the daemon to include recipient overlap information; if that preview cannot be obtained, validation still reports its own result and leaves overlap unavailable.

**Output**

- Default (valid): prints a summary including file, kind, campaign (name and key), number of valid messages, routing, follow-up count, duplicates, and overlap (or “none”), and lists any ignored fields.
- Default (invalid): prints that the file is invalid and lists issues (with row/key/field context where available) and a hint when provided.
- With `--json`: prints the full validation result object.

**Exit status:** `0` when the input is valid, `1` when it is invalid.

Use `validate` to catch problems before submitting. For the exact input contract, see `batch schema`; for a concrete starting point, see `batch example`.

### schema

Prints the input contract for batch/campaign files.

```text
downcroc batch schema
```

- Describes how downcroc detects JSON vs CSV input, the top-level structure, and the fields for campaign routing/options, messages, and follow-ups, along with notes such as CSV requiring a template and where per-message routing is specified.
- **Output:** human-readable contract text by default; with `--json`, the contract as machine-readable JSON.

Read `schema` when you need to understand what fields exist, what values are allowed, and how detection and routing work.

### example

Prints or writes starter example files.

```text
downcroc batch example [--kind {json,followups,csv,template}] [--write DIR]
```

- `--kind` selects which example to produce: `json` (a campaign), `followups`, `csv`, or `template`. If omitted, the default/example set is shown as provided.
- Without `--write`, prints the example content to stdout (or as JSON with `--json`).
- With `--write DIR`, writes the example file(s) into `DIR` (creating it if needed) and reports the written paths.

Use `example` to get a correct starting shape for a campaign, follow-up definition, CSV, or template.

### preview

Previews an input file as downcroc will interpret it, without submitting a batch.

```text
downcroc batch preview <path> [--template NAME|PATH] [--account ID] [--key KEY] [--all] [--table]
```

- `path` is a campaign file or CSV. `--template` supplies the template for CSV; `--account` pins every message to an account.
- `--key KEY` shows one message by key or row. `--all` shows every message (instead of a sample).
- `--table` shows the summary and a table view instead of message cards.

`preview` resolves the input and shows what would be sent: campaign and routing, message count/validity and approval context, follow-ups, attachments, duplicates/overlap warnings, and the message content as cards or a table. It can also show capacity/eta-related information when available.

**Output**

- Default: message card(s) for the selected/sample messages with campaign/routing/follow-up/attachment context, overlap warnings when present, and capacity/eta hints when available. If fewer than all messages are shown, it indicates how many are shown and suggests `--all`.
- With `--table`: a summary record and a recipient/subject/account table (plus warnings/ignored fields and follow-up/attachment/routing details).
- With `--json`: the preview result as JSON.

Use `preview` to confirm recipients, subjects, bodies, routing, and follow-ups before you submit.

## Campaign JSON (how to write and read it)

`downcroc batch schema` prints the machine-readable/human contract from your
installed version. The summary below reflects the same structure
(`schema: "downcroc.campaign/v1"`).

**Top level:** `schema` (optional, defaults to supported schema), optional
`producer` (free-form, stored), `campaign`, `messages`, and optional `followups`.
Unknown fields are rejected except extension keys prefixed with `x-` in supported
objects; some standard mail headers in message-like input are ignored/reported.

**`campaign`**
- `key`: string (≤128 chars), defaults to the file stem. `name`: defaults to key.
- `routing.mode`: `auto` or `fixed`. `fixed` requires `routing.account` (id or
  address). `include`/`exclude` are lists of account ids/addresses. Per-message
  account selection is not expressed in the message body (use campaign routing or
  `--account` on submit/preview/validate).
- `options`: `approval` `review`|`auto` (default `review`), `suppress_replies`
  boolean (default `true`), `reply_window_days` 0–3650 (default `60`),
  `not_before` ISO 8601 timestamp, `stop_on` list containing `reply`/`bounce`,
  `allow_duplicates` boolean (default `false`).

**`messages[]`** (required, at least one). Each message becomes a [[job]]:
- `key`: string (≤128), defaults to `m1`, `m2`, … in order.
- `to`: `{ "email": "<addr>", "name": "<optional>" }` (email required/valid).
- `subject`: required, non-empty string. `text` and/or `html` body required.
- `reply_to`: optional address. `attachments`: list of paths relative to the
  campaign file (must stay inside the source directory and meet size/validity
  rules).
- `followups`: optional per-message overrides keyed by [[follow_up_step]] key,
  each with optional `subject`, `text`, `html`, and/or `skip` (boolean). A key
  used here must match a step declared in `followups`.

**`followups[]`** (inline campaign steps): each step has `key` (unique, required),
`after_days` (1–365), `when` (`no_reply` or `always`, default `no_reply`),
optional `subject`, `text` and/or `html`, and `require_approval` (boolean, default
`false`). These define the planned sequence in the campaign; recipients may
receive per-step overrides from `messages[].followups`.

For **retroactive** follow-up definitions added to an existing batch (shared vs
payload [[follow_up_declaration]] JSON, versioning, remove/retire), see
[followups](followups.md).

## Input notes

- Input is detected as JSON or CSV by content/shape (UTF-8). CSV inputs require a
  template (`--template`); template/CSV variables and manifests are described by
  `batch schema`/examples.
- The campaign key may be derived from the file name when omitted. Message keys
  may be auto-named (`m1`, `m2`, …). Step keys are required.
- Duplicate recipients are rejected unless `campaign.options.allow_duplicates`
  is true. Overlap with recent recipients may be reported during validate/submit.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch schema` — print the input contract.
- `downcroc batch example --kind json` — print a JSON campaign example.
- `downcroc batch example --kind csv --write ./starter` — write CSV/template starter files.
- `downcroc batch validate campaign.json` — validate a campaign file.
- `downcroc batch validate rows.csv --template intro` — validate a CSV with a template.
- `downcroc batch preview campaign.json` — preview messages as cards.
- `downcroc batch preview campaign.json --table --all` — preview all messages in a table.
- `downcroc batch preview campaign.json --key m1` — preview a single message by key.

## See also

- [submit.md](submit.md) — submit a batch for sending
- [inspect.md](inspect.md) — inspect submitted batches and recipients
- [approve.md](approve.md) — approve or cancel a batch
- [../14-template/template.md](../14-template/template.md) — manage templates used with CSV inputs
- [../part-i/02-first-mail/make-a-campaign.md](../part-i/02-first-mail/make-a-campaign.md) — creating a campaign
- [../part-i/02-first-mail/read-the-preview.md](../part-i/02-first-mail/read-the-preview.md) — reading the preview
- [../part-i/06-personalise/csv-and-spreadsheets.md](../part-i/06-personalise/csv-and-spreadsheets.md) — using CSV and spreadsheets

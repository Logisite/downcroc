---
title: batch followups
commands: [batch.followup, batch.followups, batch.followups.status, batch.followups.declare, batch.followups.remove, batch.followups.retire]
flags: [batch.followup batch_id, batch.followup path, batch.followups.status batch_id, batch.followups.declare batch_id, batch.followups.declare path, batch.followups.remove batch_id, batch.followups.retire batch_id, batch.followups.declare --dry-run, batch.followups.remove --dry-run, batch.followups.retire --dry-run, batch.followups.declare --kind, batch.followup --require-approval, batch.followup --step, batch.followups.declare --step, batch.followups.remove --step, batch.followups.retire --step, batch.followup --template]
concepts: [batch, follow_up, follow_up_step, follow_up_declaration]
screens: []
---

# batch followups

A [[follow_up]] is a later reply in the same conversation, sent only when its
condition and timing still allow it. Follow-up work is organized as named
[[follow_up_step]]s on a parent campaign [[batch]]: each step defines when it is
due, the condition (`when`), the content, and whether it needs [[approval]].

There are two ways follow-up steps enter the system:

- **Inline in a campaign file** — `campaign.followups[]` defines steps for the
  campaign, and individual `messages[].followups` can override content per step
  for a specific recipient. See [prepare](prepare.md) and the campaign JSON
  format.
- **Retroactive declarations on an existing batch** — add or change steps after a
  campaign batch exists using the commands below. A [[follow_up_declaration]] can
  be shared (one definition applied per recipient, with optional overrides) or
  payload-backed (explicit per-recipient messages).

When a step becomes due and eligible, downcroc creates child follow-up work that
moves through the normal approval/queue/dispatch pipeline and stays threaded to
the original conversation. Runtime behavior, derived step status, and stop/
suppression outcomes are explained in [Pipeline](../part-iii/30-pipeline.md),
[Seats and threads](../part-iii/31-seats-and-threads.md), and
[States](../part-iii/33-states.md).

## Usage

```text
downcroc batch followup <batch_id> <path> --step STEP [--template TEMPLATE] [--require-approval]
downcroc batch followups status <batch_id>
downcroc batch followups declare <batch_id> <path> --step STEP [--kind {shared,payload}] [--version VERSION] [--dry-run]
downcroc batch followups remove <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
downcroc batch followups retire <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
```

## Commands

### `batch followup` (add a step)

```text
downcroc batch followup <batch_id> <path> --step STEP [--template TEMPLATE] [--require-approval]
```

Creates/adds a follow-up step for `batch_id` from the definition file at `path`.

- `--step STEP` (required): the step key.
- `--template TEMPLATE`: template to use for the step (when applicable).
- `--require-approval`: mark the step as requiring approval before its child work
  is dispatched.

**Output:** reports the resulting batch/follow-up state (with `--json`, the batch
as JSON).

### `batch followups status`

```text
downcroc batch followups status <batch_id>
```

Shows follow-up steps for the batch: step key, kind, state, timing (`after`/
`when`), candidate and sent counts, and child batch id when present. If no steps
exist it reports that. Per-step details/notes are shown when available.

With `--json`, prints the status report as JSON.

### `batch followups declare`

```text
downcroc batch followups declare <batch_id> <path> --step STEP [--kind {shared,payload}] [--version VERSION] [--dry-run]
```

Declares a new follow-up step, or updates an existing retroactive declaration,
for a campaign batch.

- `path`: a JSON declaration file (shared or payload-backed).
- `--step STEP` (required): the step key for this declaration.
- `--kind {shared,payload}`: force the declaration kind. If omitted, kind is
  detected from the file: a JSON array, or an object containing `messages`,
  is treated as payload; otherwise it is treated as shared.
- `--version VERSION`: required when updating an existing active declaration
  (must match the current version). Omit for a new declaration.
- `--dry-run`: evaluate and report what would happen without writing anything.

**Preconditions and rules**

- The parent must be a campaign batch (not cancelled) with at least one sent
  recipient; CSV parents do not support retroactive declarations.
- **New declaration:** the step key must not already be declared in the campaign
  snapshot and must not already have a child batch. Choose a new key if it was
  used.
- **Update:** the declaration must be `active`, must not already have a child
  batch, and you must pass the current `--version`. A version mismatch or missing
  version is rejected (retry with the reported/current version). A step that is
  no longer active, or already produced child work, cannot be rewritten in place —
  use a new key (for example `stepb`).
- On success, the declaration is stored at version 1 (new) or incremented as an
  update, and status is reported.

### `batch followups remove`

```text
downcroc batch followups remove <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
```

Removes a retroactive follow-up step before it has sent.

- Requires the declaration to exist and not be retired. A version mismatch is
  rejected when `--version` is provided.
- If a child job is currently sending, removal is rejected (wait for it to finish,
  then retire if needed).
- If any follow-up for the step has already been sent, removal is rejected; use
  `retire` instead so history is kept.
- When applied (not `--dry-run`): unsent child jobs (awaiting approval/queued/
  retry-wait, as applicable) are cancelled and the child batch/declaration state
  is ended appropriately; a declaration with no child batch is removed.
- Prompts for confirmation unless `--dry-run` or `--yes`.

### `batch followups retire`

```text
downcroc batch followups retire <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
```

Retires a step to stop further planning/activity for it while keeping sent
history.

- If the step has already sent follow-ups, retiring requires confirmation (`--yes`
  / `confirm`) unless `--dry-run`.
- When applied, the declaration is marked retired (idempotent if already retired).
- Prompts for confirmation unless `--dry-run` or `--yes`.

## Declaration and step JSON formats

### Step keys and common fields

- **Step key (`key` / `--step`)**: required, at most 128 characters, must match
  letters/digits/dots/dashes/underscores and start with a letter or digit. Keys
  must be unique where required (e.g. within campaign `followups`, and per
  declaration target). Unknown extension fields prefixed with `x-` are accepted
  in structured objects where noted.
- **Timing/condition:** `after_days` is an integer 1–365. `when` is `no_reply`
  or `always` (default `no_reply` where applicable).
- **Content:** a step/declaration needs `text` or `html` (or explicit per-
  recipient content in a payload). `subject` is optional; if omitted for a
  follow-up, it defaults to replying to the original subject (e.g. `Re: ...` as
  applicable). Body/text length is subject to intake limits.
- **`require_approval`**: boolean, default `false`.

### Inline campaign follow-ups (in the campaign JSON)

Defined in the campaign file submitted for the batch:

- `followups` (array): each item is a step object with `key`, `after_days`,
  `when`, `subject` (optional), `text` and/or `html`, `require_approval`.
- `messages[].followups` (object): per-message [[followup_override]]s keyed by
  step key. Each override may set `subject`, `text`, `html`, and/or `skip`
  (boolean). An override must reference a step key declared in `followups`.

These are part of the campaign snapshot/plan; see [prepare](prepare.md) and the
campaign examples.

### Shared declaration (`--kind shared`, or auto-detected)

A [[shared_declaration]] is a JSON object that applies one definition to eligible
recipients, with optional per-recipient overrides:

```json
{
  "after_days": 3,
  "when": "no_reply",
  "subject": "Following up",
  "text": "Hi again,\n\nJust checking in.",
  "html": null,
  "require_approval": false,
  "overrides": {
    "m1": { "skip": true },
    "m2": { "subject": "Quick check-in", "text": "..." }
  }
}
```

- Allowed fields: `after_days`, `when`, `subject`, `text`, `html`,
  `require_approval`, `overrides` (and `x-*` extensions).
- Needs `text` or `html`. `overrides` keys must match parent message keys for
  recipients in the parent batch; each override may set `subject`, `text`,
  `html`, and/or `skip`.
- Auto-detected as shared when the file is an object without a `messages` array.

### Payload declaration (`--kind payload`, or auto-detected)

A [[payload_declaration]] provides a schedule and explicit per-recipient content:

```json
{
  "followup": { "after_days": 5, "when": "no_reply", "require_approval": false },
  "messages": [
    { "key": "m1", "to": { "email": "ana@example.com" }, "subject": "Re: Hi", "text": "..." },
    { "key": "m2", "to": { "email": "bo@example.com" }, "subject": "Re: Hi", "text": "..." }
  ]
}
```

- The file may be an object with `messages` (and `followup` schedule) or a JSON
  array of messages (schedule form as required by validation). Detected as payload
  when the root is an array or an object contains `messages`.
- `followup` schedule block: `after_days` (1–365), `when` (`no_reply`/`always`,
  default `no_reply`), `require_approval` (boolean, default `false`). A scheduled
  payload declaration requires this block.
- **Coverage:** the payload must include a message for each relevant parent
  recipient (no gaps) and must not name extra recipients outside the parent.
- **Constraints:** payload declaration messages cannot carry attachments and must
  not contain template variables (`{{`/`}}`) in subject/text/html. Nested
  `followups` cannot be declared inside a payload declaration. Message matching is
  by parent source key/recipient as applicable; ignored/unsupported fields may be
  reported.
- Stored content is kept for the declaration; if it becomes missing/corrupt, the
  step must be declared again.

## Status and behavior

`followups status` (and declare/remove/retire reports) show each step with its
kind, state, timing (`after_days`, `when`), counts, child batch id, and details.
Derived step status values (e.g. `scheduled`, `pending`, `deferred`,
`awaiting_approval`, `sending`, `done`, `partial`, `skipped`,
`cancelled_child`, `retired`, `broken`, `parent_not_sent`) and their meanings are
defined in [States](../part-iii/33-states.md).

Follow-ups run relative to sent parent work, are sent as threaded replies from
the appropriate sender context, and respect stop/suppression conditions (such as
replies or bounces) and timing. A recipient/step may be skipped, suppressed,
deferred, or broken (for example a thread chain that cannot be built safely)
rather than sent; counts and reasons explain outcomes.

- **Dry run:** `--dry-run` reports without writing.
- **Confirmation:** `remove` and `retire` require confirmation unless `--dry-run`
  or `--yes` (subject to non-interactive rules).

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`,
`--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`,
`--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch followups status bat_123` — show follow-up steps for a batch.
- `downcroc batch followup bat_123 step.json --step fu2 --require-approval` — add a follow-up step from a file.
- `downcroc batch followups declare bat_123 shared.json --step fu1 --kind shared` — declare a shared step.
- `downcroc batch followups declare bat_123 payload.json --step fu1 --kind payload --dry-run` — preview a payload declaration.
- `downcroc batch followups declare bat_123 shared.json --step fu1 --version 2` — update an existing declaration at the current version.
- `downcroc batch followups remove bat_123 --step fu1 --yes` — remove an unsent step.
- `downcroc batch followups retire bat_123 --step fu1 --yes` — retire a step and keep history.

## See also

- [prepare.md](prepare.md) — campaign JSON format, schema, validation, and preview
- [submit.md](submit.md) — submit a batch (campaigns may include inline follow-ups)
- [inspect.md](inspect.md) — inspect a batch and suppression
- [../part-i/05-follow-ups/what-is-a-follow-up.md](../part-i/05-follow-ups/what-is-a-follow-up.md)
- [../part-i/05-follow-ups/the-shape-of-a-sequence.md](../part-i/05-follow-ups/the-shape-of-a-sequence.md)
- [../part-i/05-follow-ups/add-a-follow-up-to-a-batch.md](../part-i/05-follow-ups/add-a-follow-up-to-a-batch.md)
- [../part-i/05-follow-ups/change-a-sequence.md](../part-i/05-follow-ups/change-a-sequence.md)
- [../part-i/05-follow-ups/stopping-and-skipping.md](../part-i/05-follow-ups/stopping-and-skipping.md)
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md), [../part-iii/31-seats-and-threads.md](../part-iii/31-seats-and-threads.md), [../part-iii/33-states.md](../part-iii/33-states.md)

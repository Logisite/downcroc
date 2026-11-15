---
title: batch followups
commands: [batch.followup, batch.followups, batch.followups.status, batch.followups.declare, batch.followups.remove, batch.followups.retire]
flags: [batch.followup batch_id, batch.followup path, batch.followups.status batch_id, batch.followups.declare batch_id, batch.followups.declare path, batch.followups.remove batch_id, batch.followups.retire batch_id, batch.followups.declare --dry-run, batch.followups.remove --dry-run, batch.followups.retire --dry-run, batch.followups.declare --kind, batch.followup --require-approval, batch.followup --step, batch.followups.declare --step, batch.followups.remove --step, batch.followups.retire --step, batch.followup --template]
concepts: [batch]
screens: []
---

# batch followups

Follow-ups are additional messages sent after an initial (parent) message, typically as threaded replies from the same sender context. downcroc lets you define follow-up steps on a batch, inspect their status, and change them over time (declare, remove before send, retire after send).

This chapter covers `batch followup` (create/add a follow-up step) and `batch followups` (status/declare/remove/retire) — two related but distinct interfaces for managing follow-up steps.

## Usage

```text
downcroc batch followup <batch_id> <path> --step STEP [--template TEMPLATE] [--require-approval]
downcroc batch followups <status|declare|remove|retire> <batch_id> [options]
```

## Creating a follow-up step (`batch followup`)

```text
downcroc batch followup <batch_id> <path> --step STEP [--template TEMPLATE] [--require-approval]
```

Creates/adds a follow-up step for the batch from the given definition file `path`.

- `--step STEP` (required) identifies the step. Follow-up step keys are required.
- `--template TEMPLATE` can specify a template to use.
- `--require-approval` marks the step as requiring approval (as supported).

**Output:** reports the resulting batch/follow-up state (or the batch as JSON with `--json`).

## Managing follow-up steps (`batch followups`)

```text
downcroc batch followups status <batch_id>
downcroc batch followups declare <batch_id> <path> --step STEP [--kind {shared,payload}] [--version VERSION] [--dry-run]
downcroc batch followups remove <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
downcroc batch followups retire <batch_id> --step STEP [--version VERSION] [--dry-run] [--yes]
```

### status

Shows every follow-up step for a batch.

- Reports the batch and the number of steps, and lists each step with its step key, kind, state, timing (after/when), candidate/sent counts, and child batch id (when applicable). If there are no steps, it reports that. Step details/notes are shown when present.

### declare

Declares or updates a follow-up step.

- `path` points to a shared patch or payload-backed JSON definition (depending on kind).
- `--step STEP` (required) identifies the step.
- `--kind {shared,payload}` specifies the declaration kind.
- `--version VERSION` can specify the declaration version (for versioned updates/conflict control as applicable).
- `--dry-run` reports what would change without writing anything.

Declaring defines the step content/behavior for the batch. On success (or dry run) it shows the resulting follow-up status/report.

### remove

Removes a follow-up step before it has been sent (as applicable).

- `--step STEP` (required) identifies the step. `--version VERSION` may be provided when relevant.
- `--dry-run` reports what would happen without making changes.
- Without `--dry-run`, asks for confirmation unless `--yes` is given.

Removal is intended for steps that have not yet been sent; if the step cannot be removed in its current state, the operation is rejected with an error.

### retire

Retires a follow-up step (typically after send, to stop further activity for that step as applicable).

- `--step STEP` (required) identifies the step. `--version VERSION` may be provided when relevant.
- `--dry-run` reports what would happen without making changes.
- Without `--dry-run`, asks for confirmation unless `--yes` is given.

Retiring is used to end/retire a step; the exact effect depends on step state and system rules.

## Output and behavior

- **Status/report:** `followups status`, and the results of `declare`/`remove`/`retire`, render a report showing the batch, step list (step, kind, state, after/when timing, candidates/sent counts, child batch) and any per-step details. With `--json`, the report is printed as JSON.
- **Dry run:** when `--dry-run` is used, the command reports “dry run, nothing was written” and makes no changes.
- **Confirmation:** `remove` and `retire` require confirmation unless `--dry-run` or `--yes` (and non-interactive confirmation rules) apply.

## Follow-up behavior notes

- Follow-ups are scheduled/derived relative to parent messages and sent as threaded replies from the appropriate sender context. Steps have timing/conditions (for example “after N days”, and conditions such as no-reply/always as defined) and can require approval.
- Follow-ups respect stop/suppression conditions (such as replies or bounces, according to campaign/batch options and suppression rules) so recipients who have responded or should not be contacted further are not followed up inappropriately.
- Steps progress through states (declared/planned/sent/skipped/retired/removed, etc. as applicable) with counts reflecting candidates and outcomes; `followups status` is the place to see that progress.
- A step key is required. Kinds include `shared` and `payload`-backed declarations; versions can be used when updating/targeting a specific declaration.

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc batch followups status bat_123` — show follow-up steps for a batch.
- `downcroc batch followup bat_123 step2.json --step fu2 --require-approval` — create/add a follow-up step.
- `downcroc batch followups declare bat_123 fu1.json --step fu1 --kind shared` — declare a shared follow-up step.
- `downcroc batch followups declare bat_123 fu1.json --step fu1 --dry-run` — preview declaring a step.
- `downcroc batch followups remove bat_123 --step fu1 --yes` — remove a step before send.
- `downcroc batch followups retire bat_123 --step fu1 --yes` — retire a step.

## See also

- [inspect.md](inspect.md) — inspect a batch and suppression
- [submit.md](submit.md) — submit a batch (campaigns may include follow-ups)
- [prepare.md](prepare.md) — schema/examples and preview (including follow-up definitions)
- [../part-i/05-follow-ups/add-a-follow-up.md](../part-i/05-follow-ups/add-a-follow-up.md) — adding a follow-up
- [../part-i/05-follow-ups/change-a-follow-up.md](../part-i/05-follow-ups/change-a-follow-up.md) — changing follow-ups
- [../part-i/05-follow-ups/when-they-stop.md](../part-i/05-follow-ups/when-they-stop.md) — when follow-ups stop
- [../19-logs/events/jobs-dispatch.md](../19-logs/events/jobs-dispatch.md) — job/batch dispatch events
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md) — how work moves through the system

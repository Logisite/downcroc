---
title: Add a follow-up to a batch
commands: [batch.followup, batch.followups.status]
concepts: [follow_up, batch]
screens: []
---

# Add a follow-up to a batch

You do not have to decide every follow-up before you send. If a [[batch]] is
already out in the world and you realise it needs another nudge, you can add a
[[follow_up_step]] to that batch afterwards.

## Adding one step

There are two command surfaces for adding follow-ups to an existing batch:

- **`downcroc batch followup <batch_id> <path> --step STEP`** adds a step from a
  definition file (with options such as a template or requiring approval where
  supported).
- **`downcroc batch followups declare <batch_id> <path> --step STEP`** declares a
  step as a [[follow_up_declaration]] (shared or payload-backed), with support for
  kind selection, versioned updates, and dry runs.

Which file you provide depends on what you want to express. A [[shared_declaration]]
is a single JSON object that sets the schedule/condition and shared content for
everyone (and can include `overrides` for specific parent message keys). A
[[payload_declaration]] is JSON that supplies a `followup` schedule and explicit
`messages` — one per parent recipient — when each person needs their own content.

```json
// shared declaration (conceptual shape)
{
  "after_days": 4,
  "when": "no_reply",
  "text": "Just circling back on my note.",
  "require_approval": false,
  "overrides": { "m2": { "skip": true } }
}
```

```json
// payload declaration (conceptual shape)
{
  "followup": { "after_days": 4, "when": "no_reply", "require_approval": false },
  "messages": [
    { "key": "m1", "to": { "email": "ana@example.com" }, "text": "Hi Ana, ..." }
  ]
}
```

Because it belongs to the batch, the new step follows the same rules as any
other follow-up: it waits for its time, it only goes out when its condition is
still true, and it is sent as a reply by the mailbox that sent the original.
Adding it later does not change messages already sent.

## Seeing what is planned

After you add a step, run **`batch followups status`** for that batch. The
status view lists each step, its kind/state, timing, counts (candidates, sent,
etc.), and child batch when one exists. This is the place to confirm the step you
added is the one you meant and to see how it is progressing.

⤷ declaring, updating, removing, and retiring in detail:
  [change-a-sequence.md](change-a-sequence.md)
⤷ full command and JSON contract for follow-ups:
  [../../part-ii/08-batch/followups.md](../../part-ii/08-batch/followups.md)

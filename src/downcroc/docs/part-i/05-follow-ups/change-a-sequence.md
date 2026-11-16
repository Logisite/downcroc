---
title: Change a sequence
commands: [batch.followups.declare, batch.followups.remove, batch.followups.retire, batch.followups.status]
concepts: [follow_up]
screens: []
---

# Change a sequence

Plans change. After a [[batch]] has gone out you may want to adjust a
[[follow_up_step]], remove one that no longer fits, or stop planning more of it
while keeping what has already happened. downcroc lets you change a sequence, but
it treats changes carefully so you do not lose track of what was sent.

## Declaring and updating

To add or update a step later, you declare it with **`batch followups declare`**.
You give the batch, the step key, and a JSON file. The file is either a
[[shared_declaration]] (schedule/condition plus shared content, with optional
`overrides` by parent message key) or a [[payload_declaration]] (`followup`
schedule plus explicit per-recipient `messages`). You can choose the kind or let it be detected, and a dry run shows the
result without writing.

A new declaration must target a campaign batch that can accept it (not cancelled,
with sent recipients, and not a CSV parent for retroactive declarations) and the
step key must not collide with a step already declared in the campaign snapshot or
one that already has child work.

If you update an existing active declaration that has not yet produced a child
batch, you must name its current version so the edit does not race with
another. Once a step has produced child work or is no longer active, you do not
rewrite it in place — give a new step a new key.

## Removing and retiring

**Remove** is for a step that has not been sent: it cancels unsent child work for
that step and ends it (so it does not continue planning). You cannot remove a
step that has already sent, and if a child job is currently sending you must wait
and then retire if appropriate.

**Retire** stops further planning while keeping history. If follow-ups were
already sent, retiring asks for confirmation (unless dry-run/confirmed). A retired
step’s key stays taken; choose a new key for a fresh step.

Both can be previewed as a dry run and, when applied, ask for confirmation
before taking effect.

⤷ full declare/remove/retire rules, versions, and JSON formats:
  [../../part-ii/08-batch/followups.md](../../part-ii/08-batch/followups.md)
⤷ why a step might be skipped instead of sent:
  [stopping-and-skipping.md](stopping-and-skipping.md)

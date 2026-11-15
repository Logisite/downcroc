---
title: Change a sequence
commands: [batch.followups.declare, batch.followups.remove, batch.followups.retire, batch.followups.status]
concepts: [follow_up]
screens: []
---

# Change a sequence

Plans change. After a batch has gone out you may want to adjust a follow-up
step, remove one that no longer fits, or stop planning more of it while keeping
what has already happened. downcroc lets you change a sequence, but it treats
changes carefully so you do not lose track of what was sent.

## Declaring a step

To add or update a step later, you declare it with **batch followups declare**.
You give the batch, the step key, and a file that describes the step. That file
can be shared, a single patch that applies to everyone in the sequence, or a
payload that names each person and what they should receive. A dry run lets
you see how the step would look before you write it.

Declaring is how you shape a step after the fact. If you are updating a step
that already exists and has not yet created its work, downcroc asks you to be
specific about which version you are changing, so an edit never silently races
with another. Once a step has already gone on to have its own child work, you
do not rewrite that history; you give a new step a new key instead.

## Removing and retiring

Removing and retiring sound similar, but they answer different needs. **Remove**
is for a step that has not been sent: it cancels the unsent work for that step
and takes it away. You cannot remove a follow-up that has already sent to
someone, because that history is real.

**Retire** is for stopping a step while keeping what it already did. A retired
step keeps the history of any messages it sent and stops further planning. The
step's key stays taken, so if you want a fresh step later you choose a new key.
Both actions can be previewed with a dry run, and both ask for confirmation
before they take effect.

⤷ the full declare, remove, retire, and version rules:
  [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)
⤷ why a step might be skipped instead of sent:
  [stopping-and-skipping.md](stopping-and-skipping.md)

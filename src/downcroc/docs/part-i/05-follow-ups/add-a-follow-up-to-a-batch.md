---
title: Add a follow-up to a batch
commands: [batch.followup, batch.followups.status]
concepts: [follow_up, batch]
screens: []
---

# Add a follow-up to a batch

You do not have to decide every follow-up before you send. If a [[batch]] is
already out in the world and you realise it needs another nudge, you can add a
follow-up step to that batch afterwards.

## Adding one step

From the **batch** menu, **followup** lets you attach a follow-up to an
existing batch. You point it at the batch, give the step a key, and provide
the file that describes what to send and when. downcroc creates that step for
the people in the batch, as a reply in the same thread as their original
message.

Because it belongs to the batch, the new step follows the same rules as any
other follow-up: it waits for its time, it only goes out when its condition is
still true, and it is sent by the mailbox that sent the original. Adding it
later does not change the messages that have already been sent; it simply
gives the batch a next step to consider.

## Seeing what is planned

After you add a step, open **batch followups status** for that batch. The
status view lists each step, what kind it is, when it is due, and how it is
doing: whether it is scheduled, waiting, sending, done, skipped, or stopped.
This is the place to confirm that the step you added is the one you meant.

⤷ declaring and changing follow-up steps in more detail:
  [change-a-sequence.md](change-a-sequence.md)
⤷ the follow-up commands and their fields:
  [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)

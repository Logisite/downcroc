---
title: Taking work back
commands: [batch.cancel, job.cancel, job.delete]
concepts: [job, batch, queued]
screens: []
---

# Taking work back

Sometimes you change your mind. A batch went out to the wrong list, a message
should not be sent after all, or a piece of work is no longer worth keeping.
downcroc gives you ways to stop and remove work, but they are not all the same
move, and the difference matters.

## Stopping what has not left yet

If a [[job]] is still [[queued]] and has not been handed to the mail server,
you can cancel it. Cancelling tells downcroc to stop: do not send this. A
cancelled job does not leave your mailbox, because it never reached the point
of leaving.

The same idea applies to a [[batch]]. Cancelling a batch stops the work in it
that has not gone out yet. Messages that were already sent cannot be taken
back, because "sent" means the server accepted them; but the rest of the
batch can be told to stand down.

## Removing what you no longer need

Deleting is different from cancelling. Deleting removes the record of the work
from downcroc's view when it is no longer useful to keep. It is the right move
for cleaning up finished or abandoned work, not for stopping a message in
flight.

Because these moves have lasting effects, downcroc asks you to be sure before
it carries them out. That pause is there on purpose: cancelling and deleting
are decisions, not fixes, and it is worth a breath to confirm that the work
you are stopping is the work you mean.

## Choosing the gentlest move

When in doubt, reach for the gentlest move that does what you need. Pause work
if you might want it to continue later. Cancel work that must not send. Delete
work only when you are sure you do not need its record anymore. Each step down
that list is harder to undo, so it pays to start high.

⤷ every option for cancelling and deleting batches and jobs:
  [../part-ii/08-batch/holds.md](../part-ii/08-batch/holds.md)
⤷ pausing work without losing it:
  [stuck.md](stuck.md)

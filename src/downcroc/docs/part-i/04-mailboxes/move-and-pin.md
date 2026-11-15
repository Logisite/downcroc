---
title: Moving work between mailboxes
commands: [job.reassign, batch.reassign]
concepts: [job, batch]
screens: []
---

# Moving work between mailboxes

Choosing a mailbox is not always a decision you make once. A batch may need to
leave from a different address than the one you first picked, or a few
messages may need to stay with a specific mailbox while the rest can go
wherever there is room. downcroc lets you move that work without rebuilding it.

## Moving a whole batch

To send a [[batch]] from a different mailbox, use **batch reassign** and name
the mailbox it should move to. downcroc moves the work in that batch that can
still be moved and leaves finished history alone. If some of that work is
already in the middle of being sent, it refuses to move it: a message that is
in flight has to finish or wait out its turn before it can be reassigned. You
can ask for a dry run first to see what would move before you commit to it.

## Pinning and unpinning jobs

Sometimes the choice belongs to a single [[job]], not the whole batch. With
**job reassign** you can pin jobs to a mailbox so they always leave from that
address, or unpin them so downcroc routes them at send time like any other
work. You can select the jobs by id, by batch, by state, or by when they were
created, and you can run a dry run to preview the result.

Pinning is a way of saying "this one must come from here". Unpinning is the
opposite: it takes away that fixed choice and lets the scheduler decide. When
you only reassign pinned jobs to another mailbox, the jobs that were already
free to route stay that way.

## Moves that wait

A reassignment never reaches into a send that is already happening. If a job
is currently being sent, downcroc tells you and leaves it alone until its
lease is clear. That is deliberate: moving work is safe when the work is
waiting, and downcroc would rather ask you to try again than disturb something
on its way out.

⤷ the full reassign, pin, and dry-run options for jobs and batches:
  [../part-ii/08-batch/reassign.md](../part-ii/08-batch/reassign.md)
⤷ how a batch chooses a mailbox in the first place:
  [many-mailboxes.md](many-mailboxes.md)

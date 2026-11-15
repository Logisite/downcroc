---
title: When things are stuck
commands: [service, sending.show, batch.pause, batch.resume, job.pause, job.resume]
concepts: [job, batch, queued]
screens: []
---

# When things are stuck

Sometimes nothing is failing and yet nothing is moving. A queue that sits
still is not always broken; often it is waiting on a pause you asked for, a
window that has not opened, or a mailbox that has run out of room for today.
The work is to tell the difference between "stuck" and "waiting on purpose".

## Pausing is a choice, at different levels

downcroc lets you pause work at more than one level, and each level means
something different. You can pause the service itself, so the daemon stops
sending altogether. You can pause sending through the sending controls. You
can pause a single [[batch]], so the rest of your work continues while that
one group holds still. And you can pause an individual [[job]].

When something is not moving, the first question is which of these is in
effect. **status** tells you whether the daemon and sending are running. The
batch and job views tell you whether a particular piece of work is paused. A
[[queued]] job inside a paused batch is doing exactly what you told it to do:
waiting.

## Starting it again

Resuming is the mirror of pausing. If the service is paused, resume it from
the **service** menu. If a batch is paused, resume that batch. If a single job
is paused, resume that job. In each case the work picks up from where it was;
downcroc does not forget what was queued or how far it had got.

If nothing is paused and work still does not move, the reason is usually
elsewhere: a mailbox out of allowance, a sending window that is closed, or a
mailbox that cannot connect. Those are not "stuck" in the same way; they are
waiting on a condition, and the status or account screens will name it.

⤷ pausing and resuming the service and sending in full:
  [../part-ii/01-service/service.md](../part-ii/01-service/service.md)
⤷ how allowances and windows control when sends go out:
  [../part-ii/11-sending/sending.md](../part-ii/11-sending/sending.md)

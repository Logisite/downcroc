---
title: Send a file for real
commands: [batch.preview, batch.submit, batch.approve, batch.show]
concepts: [batch, job]
screens: []
---

# Send a file for real

You have a file, and you know what is in it. Before any of it turns into mail
that leaves your mailbox, downcroc gives you a few chances to look: first to
see what it understands, and then to decide that it should go ahead.

## Preview before you commit

In the **batch** menu, choose **preview** and point it at your file. Preview
reads the file and shows you what downcroc would make of it, without creating
a [[batch]] that can send. It is the safe way to answer "did I write this the
way I think I did?" because nothing is queued and nothing can leave.

```text
↑↓ move · enter edit · x clear · b back · r run · q quit
```

Read the preview the way you read a job: who it will go to, what the subject
and body say, and which campaign it belongs to. If something looks off, fix the
file and preview it again. A preview costs nothing.

## Submit and approve

When the preview looks right, choose **submit**. Submitting turns the file
into a batch of jobs. If the campaign asked for review, those jobs wait for
your approval before they send; if it asked to go ahead automatically, they
move on once they are ready.

To approve a waiting batch, choose **approve** and name the batch. Approving
is you telling downcroc, "yes, this is the work I meant." From that point the
daemon takes over: it queues the jobs and sends them according to the rules
you set.

If you want to check on a batch after you have submitted it, choose **show**
and give its name. You will see the batch, its messages, and how far along
each one is.

The same thing, typed: `downcroc batch preview <file>`,
`downcroc batch submit <file>`, and `downcroc batch approve <batch>`.

⤷ every option on the batch screens, including approving and managing batches:
  [../part-ii/08-batch/approve.md](../part-ii/08-batch/approve.md)
⤷ submitting and previewing in full detail:
  [../part-ii/08-batch/submit.md](../part-ii/08-batch/submit.md)

---
title: A quick send from a file
commands: [send, review]
concepts: [batch, job]
screens: []
---

# A quick send from a file

Sometimes you already have your messages written down in a file and you just
want to hand that file to downcroc and let it take over. You do not need to
build each [[job]] by hand in an editor; you can point at the file and send it
as one piece of work.

## Handing over the file

From the main menu choose **send**. The editor asks for the path to your
file, and it can also take a template or a specific account if your file needs
them. Fill in the path, check the other lines if they apply, and press `r`.

```text
↑↓ move · enter edit · x clear · b back · r run · q quit
```

downcroc reads the file and turns it into a [[batch]] of jobs. Depending on
how you answer the approval line, it may wait for you to look things over
before anything leaves, or it may be ready to go once you confirm. Either
way, the file you pointed at becomes work the daemon can see and track.

## Looking it over before it goes

If a send is waiting for your approval, choose **review** from the main menu.
Review shows you the batches that are ready for a decision, so you can open
one, read what will happen, and approve it when you are satisfied.

This pause is deliberate. A quick send should still be a send you understand,
and review is the moment where "quick" and "careful" meet. You see the work
as downcroc sees it before a single message leaves your mailbox.

The same thing, typed: `downcroc send <path>` to submit a file, and
`downcroc review` to see what is waiting for approval.

⤷ preparing a file and understanding what goes in it:
  [the-minimal-file.md](the-minimal-file.md)
⤷ previewing, approving, and managing a batch in full:
  [../part-ii/08-batch/approve.md](../part-ii/08-batch/approve.md)

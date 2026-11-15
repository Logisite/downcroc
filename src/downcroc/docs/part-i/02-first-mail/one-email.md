---
title: Send one email
commands: [job.create, job.send]
concepts: [job, queued, sent, vault]
screens: []
---

# Send one email

It is late in the day and one person needs one email from you, from an
address they already know. Not forty people, not a schedule, just one message
sent now.

downcroc can do that, and it treats that single message the same way it treats
a larger send: it writes it down, gives it a name, and only then sends it.
That extra step is the whole point. Once the message is written down, you can
see it, retry it if something goes wrong, and never wonder whether it left.

## Opening the editor

Start in the interactive app and choose **job**, then **create**. The screen
that opens is an editor, not a prompt that fires immediately. It shows the
fields this [[job]] needs, one per line, and waits for you.

The key bar at the bottom tells you how to move:

```text
↑↓ move · enter edit · x clear · b back · r run · q quit
```

That bar is the grammar for every editor in the app. Move to a field with the
arrows, press enter to type into it, and press enter again when it reads
right. Nothing is sent while you are here. The editor is a table you fill in;
`r` is the only key that acts on it.

Four fields matter for this first message. **account** is the mailbox it will
leave from. **to** is the person who should receive it. **subject** is the
subject line, and **text** is the body. The other fields can wait: you can
name the recipient, attach a file later, or place the job inside a [[batch]],
but none of that is required to send one plain email.

When those four lines read the way you want, press `r`.

## Reading what comes back

downcroc answers with the job it created:

```text
created job_a4f29c1b3d8e (queued)
```

Read that line slowly. `job_a4f29c1b3d8e` is the name of this message, and you
will use that name for anything you do with it next. [[queued]] means it is
written down and waiting. Nothing has gone to the mail server yet. It is
sitting by the door on purpose, because sending is a separate decision.

> Two words for this moment
>
> **queued** means written down, waiting for you or for its turn.
> **sent** means the receiving mail server accepted the message. Accepted is
> the honest word: it does not promise a human read it, only that the server
> took it.

## Sending it

Back in the **job** menu, choose **send**. The editor asks for one thing: the
job's name. Enter it and press `r`. downcroc shows you who it will go to and
asks you to confirm, because sending is the step that cannot be unsent.

When you confirm, it answers with one short line:

```text
job_a4f29c1b3d8e sent
```

When you see [[sent]], the mail server accepted the message. If you want to be
sure from the other side, look in that mailbox's Sent folder: the message is
there, in the same shape it left.

## When it waits instead

Sometimes the first run stops at the doorway. You press `r` to create the job
and downcroc answers with a line like this:

```text
alice@example.com is pending, so the send will wait until it connects
```

Read it as a sentence, not as an error. The mailbox you chose is not ready to
send yet, so downcroc refuses to pretend it can. The job is not lost and
nothing is broken; the daemon is waiting for a mailbox that can actually speak
for that address.

The fix lives in the **account** menu: pick the mailbox and choose
**connect**. Once the mailbox is connected, come back to **job** and send the
same job again. You do not retype the message, because the [[job]] kept
everything you wrote.

The same thing, typed, when you are outside the interactive app:
`downcroc job create` opens the same editor, and `downcroc job send <job>`
sends the job you named. The full list of fields lives in the jobs chapter of
Part II.

⤷ every field on the create and send screens, and every option:
  [../part-ii/09-job/job.md](../part-ii/09-job/job.md)
⤷ connecting a mailbox so it is ready to send:
  [../01-starting/connect-a-mailbox.md](../01-starting/connect-a-mailbox.md)

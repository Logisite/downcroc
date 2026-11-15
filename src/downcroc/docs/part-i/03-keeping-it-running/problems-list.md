---
title: Where problems hide
commands: [status, failed.list, doctor, logs]
concepts: [failed, vault]
screens: []
---

# Where problems hide

When something feels off, the temptation is to poke at random until it gets
better. downcroc gives you four places to look instead, and each one answers a
different kind of question. If you check them in order, you usually find the
story without guessing.

## The status screen

Start with **status**. It tells you, in one glance, whether the daemon is
running, whether the [[vault]] is unlocked, and whether the queue shows any
failed sends. Most mornings the answer is right there: everything is running,
the vault is open, and the failed count is zero. When a number or a word is
not what you expect, status tells you which direction to walk.

## The failed list

If the queue reports failures, go to **failed** and open the list. Each row
names the [[job]], the reason it failed, and how many times it has tried. This
is where a problem stops being a feeling and becomes a sentence you can read:
a mailbox that needs to be connected again, or a server that refused one
address. The list tells you what went wrong, not just that something did.

## Doctor

When the trouble is not a single message but the setup itself, run **doctor**
from the main menu. Doctor checks the installation and the pieces around it
and reports what needs attention. It is the place to look when the daemon will
not behave, when a mailbox refuses to stay healthy, or when you want a
second opinion on the ground you are standing on.

## The log

When the other three screens tell you *what* but not *why*, read the **log**.
The log is the full record of what the daemon did and noticed, in the order it
happened. It takes longer to read than a status line, which is why it comes
last, but it holds the detail the other views compress away.

Between these four, most problems stop being mysteries. You learn which screen
owns which kind of answer, and you stop guessing.

⤷ how to read and search the log, and what events mean:
  [../part-ii/19-logs/logs.md](../part-ii/19-logs/logs.md)
⤷ every check the status and doctor screens can report:
  [../part-ii/02-status/status.md](../part-ii/02-status/status.md)

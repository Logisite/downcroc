---
title: Where is my stuff?
commands: [status]
concepts: [vault]
screens: []
---

# Where is my stuff?

Because downcroc runs on your machine, everything it knows lives on your
machine too. It helps to have a picture of where that "everything" is, not so
you can move files around by hand, but so you know where to look when you
want to understand what the program is holding.

## Three places, three kinds of things

downcroc keeps its files in the standard locations your system sets aside for
programs like it. You can think of them as three places with three jobs.

There is a place for **configuration**: the settings that say how downcroc
should behave. There is a place for **data**: the things it accumulates as it
works, like the database of jobs and messages, the bodies of the mail it has
sent or stored, and the log of what it has been doing. And there is a place
for **state**: small bits of information the running daemon needs to remember
between moments.

You do not have to memorize the paths. The **status** screen tells you where
they are on your machine, and it is the easiest way to answer "where is this
kept?" without guessing.

## The vault and the log

Two things inside those places are worth naming on their own.

The [[vault]] is the locked store that holds your mailbox credentials. It sits
with downcroc's data on your machine, but the credentials inside it are
encrypted. When the daemon is stopped, the vault is locked; when you unlock it
for a run, downcroc can read what it needs to sign in.

The log is a running record of what the daemon has done and what it noticed:
sends, waits, errors, and the small decisions in between. When something looks
wrong, the log is where the full story lives, written down as it happened.

The same thing, typed: `downcroc status` shows the paths and the state of the
running daemon.

⤷ reading and understanding the log, and the log command:
  [../part-ii/19-logs/logs.md](../part-ii/19-logs/logs.md)
⤷ what the status screen reports:
  [../part-ii/02-status/status.md](../part-ii/02-status/status.md)

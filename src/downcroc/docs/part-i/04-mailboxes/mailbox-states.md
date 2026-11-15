---
title: Pausing and retiring a mailbox
commands: [account.pause, account.resume, account.archive, account.unarchive]
concepts: [vault, needs-reauth, allowance]
screens: []
---

# Pausing and retiring a mailbox

Mailboxes do not stay in the same state forever. Sometimes you want one to
rest for a while, sometimes it loses its ability to sign in, and sometimes you
are done with it altogether. downcroc gives each of these situations a
different meaning, so stopping a mailbox on purpose does not look the same as
a mailbox that is broken.

## Pausing and resuming

Pausing a mailbox is a temporary choice. From the **account** menu you can
pause one or more mailboxes, and while they are paused downcroc will not send
from them. The mailboxes are still known and connected; they are simply taking
a break.

When you are ready, you resume them the same way. Resuming puts them back in
the pool, and any work that was waiting for a mailbox with room can start
using them again. Pausing is the gentle move when you might want the mailbox
back soon.

## When a mailbox cannot sign in

A mailbox can also stop being usable without you asking for it. If its
credential expires or stops working, it becomes [[needs-reauth]]: downcroc
knows the address, but it can no longer open the door. That is different from
a pause. A paused mailbox is waiting on you; a mailbox that needs
re-authentication is waiting for a working sign-in.

The answer there is to connect it again, not to pause it. Once it can sign in,
it returns to normal.

## Putting a mailbox away

If you no longer want to use a mailbox with downcroc, you can archive it.
Archiving takes it out of the active set so new work is not routed to it, but
it keeps its history. If you ever need it again, you can bring it back.

Removing a mailbox entirely is a stronger step, because it means you do not
expect downcroc to work with it anymore. As with any lasting change, it is
worth being sure which one you mean: pause for a rest, archive to put it away,
and only remove it when you are finished with it.

⤷ every account state and the commands that change it:
  [../part-ii/07-account/account.md](../part-ii/07-account/account.md)
⤷ fixing a mailbox that cannot sign in:
  [../01-starting/gmail.md](../01-starting/gmail.md)

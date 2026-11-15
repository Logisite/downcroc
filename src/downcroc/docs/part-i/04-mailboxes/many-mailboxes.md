---
title: Using more than one mailbox
commands: [account.list, batch.reassign]
concepts: [job, batch, allowance]
screens: []
---

# Using more than one mailbox

One mailbox can send a lot of mail, but it does not have to send all of it.
When you connect more than one mailbox, downcroc can spread the work between
them, which keeps any single address from carrying the whole load and helps
your sending look like the steady work of several people instead of one.

## Letting downcroc choose

If you do not name a specific mailbox for a send, downcroc can choose one for
you from the mailboxes that are ready. It looks at what each mailbox is
allowed to do and picks one that has room. You do not have to plan the split
message by message; you decide that more than one mailbox is available, and
the daemon does the balancing.

This is the easy path when you care that the mail goes out, but you do not
care which of your own addresses it comes from. Each mailbox still follows its
own [[allowance]] and its own limits, so adding mailboxes gives you more room
to work with, not a way around the rules.

## Choosing for yourself

Sometimes the address matters. A message may need to come from a particular
person, or a whole [[batch]] may belong to one mailbox. In those cases you can
tell downcroc which mailbox to use, either when you create the work or by
moving it later.

Moving work between mailboxes is something you can do on purpose: you can
reassign a batch, or pin certain jobs to the account they should leave from.
The important thing is that the choice stays visible. When a message comes
from a specific mailbox, it is because you or the routing asked for it, not by
accident.

⤷ moving and pinning work between mailboxes:
  [move-and-pin.md](move-and-pin.md)
⤷ how allowances shape the spread across mailboxes:
  [tune-a-mailbox.md](tune-a-mailbox.md)

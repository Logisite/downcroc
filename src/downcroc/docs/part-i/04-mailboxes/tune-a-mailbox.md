---
title: Tuning a mailbox
commands: [account.policy, sending.set, sending.show, account.transport]
concepts: [allowance, sending_window, jitter, max_in_flight]
screens: []
---

# Tuning a mailbox

A connected mailbox works fine with its defaults, but you may not want every
mailbox to behave the same way. One address might be safe to send from often,
another only during office hours, and a third should rest for the afternoon.
Tuning a mailbox is how you tell downcroc what "a comfortable pace" means for
that address.

## The send policy

From the **account** menu, open **policy**. This is where you shape how a
mailbox sends. You can set a daily [[allowance]], the number of messages that
mailbox may send in a local day. You can set a [[sending_window]], the span of
local hours when sending is allowed, so mail goes out when people are awake
rather than in the middle of the night. You can set [[jitter]], the gap
downcroc leaves between one send and the next, and [[max_in_flight]], how many
sends that mailbox may have in progress at once.

When you change a value with **policy set**, you are placing an override on
that mailbox. If you want the change to last only for a while, add a duration
with `--for`, such as `2h` or `7d`; downcroc treats it as a temporary
override and shows when it expires. You can remove the lasting override with
**clear**, or drop only the temporary one with **clear-temporary**, and the
mailbox falls back to the values beneath it.

## A temporary change for all sending

Some days you want to slow everything down, not just one mailbox. The
**sending** menu controls the global send policy. You can look at it with
**show**, change it with **set**, and, just like a mailbox, make a change
temporary with `--for`. Clearing it removes the global override. This is the
lever to reach for when the situation affects all of your mail at once.

## The path the mail travels

Each mailbox also has a transport, the route it uses to deliver mail. Most of
the time you never touch it, because downcroc sets a sensible one when you
connect the account. If you need to, the **account transport** menu lets you
list, add, change, remove, or test a transport for a mailbox. Treat this as
careful tuning: the policy decides *when* and *how often* a mailbox sends,
while the transport decides *how* it gets out the door.

⤷ every policy field, its units, and how global, account, and batch limits
  combine: [../part-ii/11-sending/sending.md](../part-ii/11-sending/sending.md)
⤷ the full account and transport commands:
  [../part-ii/07-account/account.md](../part-ii/07-account/account.md)

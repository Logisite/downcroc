---
title: When a mailbox breaks
commands: [account.show, account.connect, account.verify, account.transport, doctor]
concepts: [needs-reauth, vault]
screens: []
---

# When a mailbox breaks

A mailbox that worked yesterday can stop working today, and it usually does so
for an ordinary reason. The credential expired, the password changed, or the
route it uses to send or read mail no longer answers the way it should. When
that happens, downcroc does not guess; it marks the mailbox so you can see
what is wrong and fix the cause.

## When it needs to sign in again

The most common break is [[needs-reauth]]. downcroc still knows the mailbox,
but it can no longer prove who it is, so it will not try to send from it. You
will see the state on the account and in the status screen. The fix is to
connect the mailbox again: open **account**, choose **connect**, and complete
the sign-in. Once a working credential is back, the mailbox can return to
normal.

If this keeps happening to a Gmail mailbox, the lasting fix is usually in how
that mailbox was set up. A Gmail app left in testing lets its permission
expire after about a week, so publishing the app is what makes the sign-in
stick.

## When the route is the problem

Sometimes the sign-in is fine but the way mail travels is not. **account
verify** checks that the mailbox can sign in now, and the **account transport**
menu lets you inspect the routes it uses to send and test one when you need to.
If a check fails, the message it reports points at the part that could not be
reached, which is a better place to start than changing things at random.

## Asking for a second opinion

If you have reconnected the mailbox and its transport looks right but it still
will not behave, run **doctor**. Doctor checks the pieces around the
installation and reports what needs attention. It cannot fix a remote server
for you, but it can tell you whether the trouble is in your setup or somewhere
downcroc depends on.

A broken mailbox is frustrating, but it is rarely mysterious. Read the state it
reports, repair the sign-in or the route it names, and test before you trust
it with work again.

⤷ reconnecting a Gmail mailbox and publishing its OAuth app:
  [../01-starting/gmail.md](../01-starting/gmail.md)
⤷ the full account commands, including test and transport:
  [../part-ii/07-account/account.md](../part-ii/07-account/account.md)
⤷ the checks doctor can report:
  [../part-ii/02-status/status.md](../part-ii/02-status/status.md)

---
title: When something looks wrong
commands: [status, failed.list, account.connect]
concepts: [failed, needs-reauth, job]
screens: []
---

# When something looks wrong

Most days the daily round ends with nothing to do. Some days the status screen
shows a failed count that was not there yesterday. This page walks one of
those days from the first hint to the moment it is settled, so the path feels
familiar before you need it.

## The first hint

You open **status** and the last line reads differently than usual:

```text
queue     34 sent, 1 failed
```

One failed send is not a crisis. It means one [[job]] could not be delivered
and downcroc wrote down why. Your next move is not to fix anything yet; it is
to read.

## Reading the reason

From the main menu choose **failed**, then **list**. The row you see names the
job, the recipient, and a short reason:

```text
job          recipient         code                   attempts  failed_at
job_7b21e9   ana@example.com   account_needs_reauth   1         09:04
```

That reason, `account_needs_reauth`, is the story in one word. The mailbox
this message was meant to leave from can no longer sign in. The address is
fine and the message is fine; the permission to send has expired. This is what
[[needs-reauth]] looks like in practice.

## Putting it right

The fix belongs to the mailbox, not to the message. Open **account**, choose
the mailbox that lost its permission, and run **connect** to sign it in again.
If this is a Gmail mailbox that keeps expiring, the lasting fix is to publish
its OAuth app so the permission stops timing out every week.

Once the mailbox is connected, the waiting [[job]] still has everything it
needs. downcroc can try it again, and you did not have to rewrite a word. The
problem was never the message; it was the door it was trying to leave through.

## Knowing you are done

Go back to **status**. When the failed count returns to what you expect and
the mailbox shows as healthy, the story is over. You found the hint, read the
reason, fixed the cause, and let the work continue.

Not every failure has this cause, but the shape of the response is the same:
notice, read, understand whose problem it is, and act on that. The failed list
tells you the reason; the reason tells you where to go.

⤷ every failure reason and what each one asks you to do:
  [../part-ii/10-failed/failed.md](../part-ii/10-failed/failed.md)
⤷ reconnecting a Gmail mailbox that keeps expiring:
  [../01-starting/gmail.md](../01-starting/gmail.md)

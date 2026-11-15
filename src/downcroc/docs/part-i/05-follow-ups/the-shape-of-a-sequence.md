---
title: The shape of a sequence
commands: [batch.followups.status]
concepts: [follow_up]
screens: []
---

# The shape of a sequence

A follow-up is described as a step: wait this long, then send this, but only if
it still makes sense. When you read or write a sequence, you are really reading
a few simple decisions repeated for each step.

## When and whether

Every step waits for a number of days before it becomes due. The `after_days`
value is that wait, counted from the point the step follows. The `when` value
says the condition. With `no_reply`, the step goes out only if the thread has
stayed quiet; if the person has already answered, there is nothing to follow up
on.

A step can also ask for your approval before it sends. Marking it to require
approval means downcroc will prepare the follow-up but wait for you to review
it, which is useful when the later message should be checked by a person.

## Naming a step

Each step has a key, a short name that tells it apart from the others in the
same sequence. The key is how you refer to that step later when you want to
look at it, change it, or stop it. Because the key identifies the step, two
steps in the same sequence do not share one, and a key that has already been
used for a step stays taken.

## Following up as replies

A follow-up does not start over. It is sent as a reply on the original thread,
to the person the original message went to, from the mailbox that sent it.
That is what keeps a sequence feeling like one conversation rather than a
string of unrelated notes.

You can describe steps up front in a campaign file, or add and manage them on a
batch after it exists. Either way, the shape is the same: a named step, a wait,
a condition, and the message it will send.

⤷ adding a follow-up to work that already exists:
  [add-a-follow-up-to-a-batch.md](add-a-follow-up-to-a-batch.md)
⤷ stopping, skipping, and seeing why a step did not send:
  [stopping-and-skipping.md](stopping-and-skipping.md)

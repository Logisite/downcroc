---
title: What a follow-up is
commands: [batch.followups]
concepts: [follow_up, batch, job]
screens: []
---

# What a follow-up is

A follow-up is not a new message to a stranger. It is another note in the same
conversation, sent later, to someone who has not answered yet. In downcroc a
[[follow_up]] is always a reply to the message that started the [[thread]], so it
arrives where the first message arrived and reads as part of the same exchange.

## It follows the original

Because a follow-up belongs to the original send, it inherits the things that
make the thread make sense. It goes to the same person, it replies on the same
thread, and it leaves from the mailbox that actually sent the parent message.
You do not choose a different mailbox for a follow-up; if the thread must come
from somewhere else, you move the work that started it.

This is why follow-ups live with a [[batch]]. They are the later steps of work
you have already begun, not a separate campaign. When you look at a batch, you
can see not only what has gone out, but what is still planned to go out after
it.

## Planned, named, and conditional

A follow-up sequence is made of named [[follow_up_step]]s. Each step says how
long to wait (`after_days`), under what condition to send (`when` — for example
only if there was no reply), what to say, and whether it needs [[approval]].
downcroc keeps track of that plan for each person. If the person replies or the
reason to follow up disappears, the step can be skipped or [[suppressed]] instead
of sent, so “nothing sent” can be the correct outcome.

## Where the definition lives

You can describe steps up front in the campaign JSON (the `followups` list, with
optional per-message overrides), or add/change them later on an existing batch as
a [[follow_up_declaration]]. Declarations come in two forms: a [[shared_declaration]]
(one definition applied with optional overrides) or a [[payload_declaration]]
(explicit per-recipient messages on a schedule). The shape and rules differ, and
Part II spells them out; the next pages build up how to read and write them.

⤷ the shape of a step and how to write it:
  [the-shape-of-a-sequence.md](the-shape-of-a-sequence.md)
⤷ every follow-up command and JSON form in full:
  [../../part-ii/08-batch/followups.md](../../part-ii/08-batch/followups.md)

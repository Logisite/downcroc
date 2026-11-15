---
title: Stopping and skipping follow-ups
commands: [batch.followups.status, batch.suppression]
concepts: [follow_up]
screens: []
---

# Stopping and skipping follow-ups

A follow-up is a promise to send later, but only if it still makes sense. Much
of the time the right thing for a follow-up to do is nothing at all. downcroc
watches for the reasons to stop and records why a step was skipped, so you can
trust that a quiet thread means "handled", not "forgotten".

## When a follow-up should not go out

A campaign can say what should stop a follow-up. If `stop_on` includes a reply,
a person who has already answered will not get the next nudge. If it includes
a bounce, a message that could not be delivered will not be chased. With
`suppress_replies` on, downcroc also avoids following up with someone who has
replied within the reply window, so you do not keep talking after the
conversation has moved on.

These are the ordinary reasons a step is skipped: the person replied, the
address bounced, the recipient was suppressed, or the parent work was
cancelled. A skipped follow-up is not a failure. It is the sequence noticing
that sending more would be the wrong move.

## Seeing what was held back

The **batch followups status** view shows each step and the state it ended up
in, including steps that were skipped or stopped. If you want to understand
who would be held back because they replied, **batch suppression** shows a
preview of the suppressed recipients for a batch.

Reading these views turns "did it follow up?" into a clear answer. You can see
which people moved on, which steps finished, and which ones stood down on
purpose.

⤷ the follow-up states and suppression fields in full:
  [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)
⤷ where reply handling and the reply window are set:
  [../part-ii/08-batch/submit.md](../part-ii/08-batch/submit.md)

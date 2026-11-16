---
title: Stopping and skipping follow-ups
commands: [batch.followups.status, batch.suppression]
concepts: [follow_up]
screens: []
---

# Stopping and skipping follow-ups

A follow-up is a promise to send later, but only if it still makes sense. Much
of the time the right thing for a [[follow_up]] to do is nothing at all. downcroc
watches for the reasons to stop and records why a [[follow_up_step|step]] was
skipped, [[suppressed]], deferred, or broken, so you can trust that a quiet
thread means “handled”, not “forgotten”.

## When a follow-up should not go out

Campaign options say what should stop further messages: `stop_on` can include
`reply` and/or `bounce`, and `suppress_replies` with `reply_window_days` avoids
nudging someone who has replied within that window. A step’s `when` (`no_reply`
or `always`) also controls whether a reply blocks that step.

Common outcomes: the person replied or bounced, the recipient was suppressed, the
step was not yet due, there was nothing eligible to send, the parent work was not
sent, or the thread chain could not be built safely. A skipped or suppressed
follow-up is not a [[failed]] job — it is the sequence standing down on purpose
or because it cannot safely continue.

## Seeing what was held back

**`batch followups status`** shows each step’s derived state, timing, counts, and
child batch, so you can tell what is scheduled, waiting, sent, skipped,
cancelled, retired, or broken and why. **`batch suppression`** previews
suppressed recipients for a batch (with reasons where available).

Reading these views together turns “did it follow up?” into a clear answer.

⤷ follow-up states, counts, and command/JSON details:
  [../../part-ii/08-batch/followups.md](../../part-ii/08-batch/followups.md)
⤷ status words across the system:
  [../../part-iii/33-states.md](../../part-iii/33-states.md)
⤷ reply handling and options on submit:
  [../../part-ii/08-batch/submit.md](../../part-ii/08-batch/submit.md)

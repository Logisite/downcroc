---
term: follow-up step
summary: one named, timed follow-up action in a sequence
aliases: [step]
---

A follow-up step is a single planned follow-up in a sequence: it has a key, a wait (`after_days`), a condition (`when`, such as `no_reply` or `always`), the message content to send, and whether it requires approval.

Steps can be defined up front in a campaign’s `followups` list or added later as a follow-up declaration on a [[batch]]. Each step is identified by its key within that sequence/parent context.

More:
- [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)
- [../part-i/05-follow-ups/the-shape-of-a-sequence.md](../part-i/05-follow-ups/the-shape-of-a-sequence.md)

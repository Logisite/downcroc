---
term: follow-up override
summary: a per-message change for a specific follow-up step
aliases: [override]
---

A follow-up override customizes what a particular recipient receives for a named follow-up step. In a campaign JSON, overrides live under a message’s `followups` object keyed by step key (and may set `subject`, `text`, `html`, or `skip`). In a shared declaration, overrides are provided in the declaration’s `overrides` object keyed by parent message key.

Overrides must refer to known step/message keys as applicable.

More:
- [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)

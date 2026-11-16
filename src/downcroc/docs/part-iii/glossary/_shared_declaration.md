---
term: shared declaration
summary: a follow-up declaration that applies one shared message (with optional per-recipient overrides)
---

A shared declaration is a kind of [[follow-up declaration]] whose JSON defines the step schedule/condition and shared content (`text`/`html`, optional `subject`, `require_approval`) plus optional `overrides` keyed by parent message key. downcroc applies that shared content to eligible recipients, using any override for a specific recipient.

More:
- [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)

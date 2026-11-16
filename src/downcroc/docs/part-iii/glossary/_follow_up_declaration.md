---
term: follow-up declaration
summary: a follow-up step added or updated on an existing batch after the fact
aliases: [declaration]
---

A follow-up declaration defines a follow-up step for an existing campaign [[batch]] outside the original campaign file (using `batch followups declare` / related commands). Declarations can be **shared** (one template/patch applied per recipient with optional overrides) or **payload-backed** (explicit per-recipient messages with a schedule).

Declarations are versioned, can be declared before they run, removed before send, or retired to stop further planning while keeping history, subject to state and conflict rules.

More:
- [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)
- [../part-i/05-follow-ups/change-a-sequence.md](../part-i/05-follow-ups/change-a-sequence.md)

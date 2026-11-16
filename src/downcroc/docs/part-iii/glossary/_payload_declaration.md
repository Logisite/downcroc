---
term: payload declaration
summary: a follow-up declaration that supplies explicit per-recipient follow-up messages and a schedule
aliases: [payload]
---

A payload declaration is a kind of [[follow-up declaration]] whose JSON provides a `followup` schedule block and a `messages` list (or an array/document form accepted by the parser) with one message per parent recipient. Each recipient gets the explicitly provided content for that step.

Payload declarations must cover the parent recipients (no gaps) without naming extras, and have stricter constraints than campaign messages (for example no attachments and no template variables in declaration payload messages).

More:
- [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)

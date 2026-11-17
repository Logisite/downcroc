---
term: backfill
summary: filling in message details downcroc did not record when the mail was sent
---

Backfill is a repair job that fills in missing conversation ids for older sent
mail, so replies to those messages stay in the same [[thread]]. It only writes
the missing id; it does not resend, move, or change the mail.

More:
- [backfill log events](../part-ii/19-logs/events/backfill.md)

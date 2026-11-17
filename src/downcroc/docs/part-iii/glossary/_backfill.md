---
term: backfill
summary: filling in message details downcroc did not record when the mail was sent
---

Backfill is a repair job that fills in missing conversation ids for older sent
mail, so replies to those messages stay in the same [[thread]]. It only writes
the missing id; it does not resend, move, or change the mail.

A hole ends one of three ways. It is filled, it is missing because the
provider confirmed the message is gone, or it is unresolved because downcroc
could not check, for example while an account is [[needs-reauth]]. You can see
which with `downcroc backfill status` and `downcroc backfill explain`, and
push a hole back into the next pass with `downcroc backfill retry`.

More:
- [backfill command](../part-ii/27-backfill/backfill.md)
- [backfill log events](../part-ii/19-logs/events/backfill.md)

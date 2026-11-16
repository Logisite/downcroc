---
term: max_in_flight
summary: how many sends a mailbox may have in progress at once
---

Max in flight is the number of sends a mailbox may have underway at the same
time. Keeping this low spaces work out; raising it allows more sends to run in
parallel for that mailbox, within the limits of how sending is configured.

More:
- [../part-ii/11-sending/sending.md](../part-ii/11-sending/sending.md)

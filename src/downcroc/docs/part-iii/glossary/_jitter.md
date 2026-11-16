---
term: jitter
summary: the gap downcroc leaves between one send and the next
---

Jitter is the pause downcroc waits between sending messages from a mailbox. By
spacing sends out instead of firing them back to back, it keeps the pace
steady and more like the rhythm of a person writing mail.

A mailbox's send policy sets a minimum and maximum gap, and downcroc chooses a
wait in that range between sends.

More:
- [../part-ii/11-sending/sending.md](../part-ii/11-sending/sending.md)

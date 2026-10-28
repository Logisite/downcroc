# 09 - Replies land on the right batch

**What to build:** inbound mail is attributed. Threading follows `In-Reply-To` and `References`
with a subject fallback, delivery reports are classified as bounces and never as replies, and each
reply is confirmed by headers or marked probable. A batch reports `N inbound (M replies)`. Replies
outside the window still attach and still suppress, and a restart never double counts.

**Blocked by:** 05, 08

**Status:** ready-for-agent

- [ ] a reply to a sent message is confirmed and increments the correct batch once
- [ ] a bounce is counted as a bounce and leaves the reply count alone
- [ ] two replies from the same person both attach, and suppression is set once
- [ ] a reply arriving after the window attaches and suppresses
- [ ] a reply with no threading headers falls back to the subject and is marked probable
- [ ] restarting after ingest does not change any count
- [ ] the batch counter endpoint agrees with the message rows

**Logs:** the events this ticket introduces.

- `message.classified` kind, confidence, headers
- `thread.linked` thread, method
- `reply.attributed` batch, job, confirmed
- `reply.unattributed` message, reason
- `dsn.parsed` job, status, code
- `suppression.added` address, reason

**Commit:** `feat(replies): add threading, dsn class, batch counters`

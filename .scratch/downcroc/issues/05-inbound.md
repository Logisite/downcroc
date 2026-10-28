# 05 - Inbound mail arrives and stays

**What to build:** one watcher thread per connected account keeps INBOX current. It tracks
UIDVALIDITY, idles with a timeout, ingests new messages, dedupes on the server identity, stores
bodies and headers, files attachments in the content store, and builds threads. Mailbox endpoints
list and read. A restart resumes from the stored cursor without re-ingesting.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] mail sent to the account appears within seconds while the daemon idles
- [ ] restart does not duplicate a single message
- [ ] a UIDVALIDITY change triggers a resync instead of silent loss
- [ ] an attachment lands in the content store with a recorded hash
- [ ] the watcher thread performs no database writes of its own
- [ ] a watcher that dies is restarted, and the reason is visible
- [ ] disconnecting an account stops its watcher and leaves the cursor intact

**Logs:** the events this ticket introduces.

- `watcher.started` account, host, uidvalidity
- `watcher.idle_wake` reason
- `imap.fetch` account, count, duration_ms
- `message.ingested` message_id, uid, thread
- `attachment.stored` filename, bytes, sha256 prefix
- `watcher.stopped` reason, retry_in_s

**Commit:** `feat(inbound): add imap watcher, ingest, uid cursor`

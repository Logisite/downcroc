# 06 - One message out, proven

**What to build:** a job can be sent as a real message. The MIME body is assembled, a Message-ID
is minted and recorded before the wire, SMTP sends with XOAUTH2, and the job moves to `sent`.
The window where the server accepted but the daemon died is closed by searching the Sent folder
for the minted Message-ID on the next start. Duplicates never happen.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] a message sent to a second mailbox arrives with correct HTML and text parts
- [ ] the minted Message-ID matches what the recipient sees and what is stored
- [ ] killing the daemon between accept and commit, then restarting, sends nothing new and records the send
- [ ] killing before accept, then restarting, sends exactly once
- [ ] a temporary SMTP failure is classified transient and a permanent one is not retried
- [ ] an expired access token is refreshed inside the send
- [ ] the job row is the only place send state lives

**Logs:** the events this ticket introduces.

- `job.send_start` job, account, attempt
- `smtp.connected` host, duration_ms
- `smtp.accepted` job, message_id, duration_ms
- `smtp.rejected` code, transient
- `job.sent` job, message_id, duration_ms
- `job.reconciled` job, message_id, found

**Commit:** `feat(outbound): add mime build, smtp send, sent reconcile`

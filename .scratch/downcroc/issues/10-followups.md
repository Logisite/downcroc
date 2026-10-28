# 10 - Follow-ups inherit everything

**What to build:** the follow-up engine. Steps declared with a campaign become due relative to the
previous step that actually sent for each recipient. When due, the daemon forces an inbound sync
for that account, excludes repliers, bounces, and suppressed addresses, derives a batch, inherits
the parent job's account, and sets `In-Reply-To` and `References` into the same thread. Content can
be the declared step, a per-message override, or a follow-up payload of ready messages or CSV plus
template. Derivation is idempotent across restart, and one reply or bounce cancels every remaining
step for that person.

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] a campaign with two follow-up steps sends only to non-repliers, each after its delay
- [ ] `after_days` counts from the previous step that sent, not from submit
- [ ] a reply before a step is due cancels all remaining steps for that recipient
- [ ] a bounce cancels all remaining steps for that recipient
- [ ] the follow-up uses the parent job's account, even when other accounts have more allowance
- [ ] the follow-up arrives in the same thread: `In-Reply-To` is the previous outbound
      `Message-ID`, and `References` carries the chain
- [ ] when a step fails, the next step anchors to the most recent step that actually sent
- [ ] a per-message override replaces the shared step content, and `skip: true` opts one recipient
      out
- [ ] a suppressed address is excluded even if the payload lists it again
- [ ] a CSV plus template follow-up works against a JSON campaign, and ready messages work against
      a CSV campaign
- [ ] extras are reported and eligible recipients without content are an error
- [ ] restarting at the due moment creates no duplicate step
- [ ] a step marked `require_approval` waits for approval, the rest run when due
- [ ] follow-up batches report their own inbound counts

**Logs:** the events this ticket introduces.

- `followup.planned` batch, step, candidates, replied, bounced, suppressed
- `followup.created` batch, jobs, source batch, step
- `followup.deferred` batch, step, reason
- `followup.skipped` job, step, reason
- `followup.sync_failed` account, step, defer_s

**Commit:** `feat(followups): add derived steps, mixed sources, thread headers`

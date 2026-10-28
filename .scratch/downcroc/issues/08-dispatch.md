# 08 - The queue drains itself

**What to build:** the dispatcher drains jobs on its own. Eligibility comes from the active window
and the per-account daily allowance, accounts are picked at random weighted by remaining allowance,
sends are spaced by configurable jitter, concurrency is bounded, and each job is leased while it is
in flight. Transient failures retry with exponential backoff up to a configured count; permanent
failures land in `failed.jsonl` and the failure table at one boundary, and can be listed and
retried.

**Blocked by:** 06, 07

**Status:** ready-for-agent

- [ ] 1,000 jobs across several accounts drain without any account exceeding its daily allowance
- [ ] nothing sends outside the configured window
- [ ] `kill -9` mid drain, then restart, produces no duplicate and no silently lost job
- [ ] an expired lease is reclaimed rather than leaving a job stuck
- [ ] transient errors retry with growing gaps, permanent errors do not
- [ ] each permanent failure appears exactly once in both the file and the table
- [ ] retrying a failure sends exactly once and clears the failure

**Logs:** the events this ticket introduces. Per tick detail stays at debug, so the default file
shows one line per send and one per failure, not one per loop.

- `dispatch.cycle` picked, sent, deferred, duration_ms (debug)
- `dispatch.idle` reason: window closed, allowance spent, nothing due
- `dispatch.spacing` delay_ms
- `job.leased` job, account (debug)
- `quota.consumed` account, used, limit
- `job.retry` job, attempt, in_s, code
- `job.failed` job, code, attempts

**Commit:** `feat(dispatch): add tick loop, allowance, leases, failure log`

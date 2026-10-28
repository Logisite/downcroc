# 11 - Numbers that outlive their rows

**What to build:** activity is stored instead of computed on read. Hourly and daily rows are
account scoped, batch counters are kept, and summary endpoints read them. A rebuild recomputes
everything from jobs and messages. Retention prunes jobs, mail and hourly rows on their own
schedules while the stored history stays. The invariant between stored sends and job rows is
checked after a rebuild.

**Blocked by:** 08, 09

**Status:** ready-for-agent

- [ ] a send increments the hourly and daily row for its account
- [ ] a reply increments inbound on the same day
- [ ] pruning expired jobs and mail leaves every total unchanged
- [ ] a rebuild produces the same numbers as the live counters
- [ ] the invariant holds after a rebuild and reports a mismatch when one is planted
- [ ] summaries return per-account and total figures for a requested range

**Logs:** the events this ticket introduces. Increments are debug, rebuilds and prunes are info.

- `stats.increment` account, field, value (debug)
- `stats.rebuilt` since, rows, duration_ms
- `stats.invariant` outcome, stored, rows
- `retention.pruned` table, count, bytes

**Commit:** `feat(stats): add stored activity, rebuild, retention`

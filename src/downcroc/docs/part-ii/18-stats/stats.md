---
title: stats
commands: [stats, stats.summary, stats.hourly, stats.daily, stats.batches, stats.accounts, stats.pending, stats.rebuild, stats.prune]
flags: [--from, --since, --to, --account]
concepts: []
screens: []
---

# stats

`stats` reports stored activity and queue totals: sent/failed/received/replies/bounces/suppressed over time, per batch or account, plus pending-work ETA. It can also rebuild or prune activity rows.

All reporting subcommands accept a time/account scope where applicable: `--from`/`--to` (dates) to bound the range, `--since` as a relative window (seconds) mapped to a start date when `--from` is not given, and `--account` to filter by account.

## Usage

```text
downcroc stats <action> [options]
```

Actions: `summary`, `hourly`, `daily`, `batches`, `accounts`, `pending`, `rebuild`, `prune`.

## Reporting actions

### summary

Shows stored totals for the selected range.

```text
downcroc stats summary [--from DATE] [--to DATE] [--since SECONDS] [--account ACCOUNT]
```

- Reports the range (`from`/`to`) and total counts (sent, failed, received, replies, bounces, suppressed). Includes inbound/stale-watcher information when available and per-account totals when present.
- Also shows the current pending ETA/capacity view (remaining work, lanes/seats/serial configuration, finish estimate, or a blocked reason) as part of the summary.

With `--json`, prints the summary together with `pending_eta`.

### hourly

Shows hourly activity.

```text
downcroc stats hourly [--from DATE] [--to DATE] [--since SECONDS] [--account ACCOUNT]
```

- Prints the range and a table of hourly rows by account with sent/failed/received/replies/bounces/suppressed counts.

With `--json`, prints the hourly data.

### daily

Shows daily activity.

```text
downcroc stats daily [--from DATE] [--to DATE] [--since SECONDS] [--account ACCOUNT]
```

- Prints the range and a table of daily rows by account with quota limit and sent/failed/received/replies/bounces/suppressed counts.

With `--json`, prints the daily data.

### batches

Shows batch totals.

```text
downcroc stats batches [--from DATE] [--to DATE] [--since SECONDS] [--account ACCOUNT]
```

- Prints the range and a table of batches (batch id, name, kind, sent, failed, replies, reply rate).

With `--json`, prints the batch totals.

### accounts

Shows account totals.

```text
downcroc stats accounts [--from DATE] [--to DATE] [--since SECONDS] [--account ACCOUNT]
```

- Prints the range and a table of accounts (account id, address, used/reserved/available allowance, and sent/failed/received/replies/bounces/suppressed counts).

With `--json`, prints the account totals.

### pending

Shows pending work and its ETA.

```text
downcroc stats pending
```

- Reports the pending/queue state: remaining work, lanes/seats and whether sending is serial, an estimated finish time when available, or a blocked reason/state when work cannot proceed normally.

With `--json`, prints the pending payload.

## Maintenance actions

### rebuild

Rebuilds activity rows.

```text
downcroc stats rebuild [--since YYYY-MM-DD]
```

- Rebuilds stored activity/statistics rows. `--since` (first date, `YYYY-MM-DD`) limits how far back to rebuild.
- Reports how many rows were rebuilt and the duration.

With `--json`, prints the rebuild result.

### prune

Prunes expired activity rows.

```text
downcroc stats prune [--yes]
```

- Removes expired activity/statistics rows according to retention rules.
- Reports the bytes reclaimed and per-table counts.

With `--json`, prints the prune result. (Confirmation behavior follows standard flags where applicable.)

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc stats summary --from 2026-10-01` — totals and pending ETA from a date.
- `downcroc stats pending` — show pending work and ETA.
- `downcroc stats daily --since 604800` — daily activity over roughly the last week.
- `downcroc stats accounts` — per-account totals and allowance.
- `downcroc stats batches` — per-batch outcomes.
- `downcroc stats rebuild` — rebuild activity rows.
- `downcroc stats prune` — prune expired activity rows.

## See also

- [../02-status/status.md](../02-status/status.md) — one-screen health and queue summary
- [../15-mail/mail.md](../15-mail/mail.md) — browse/prune ingested mail (separate from stats rows)
- [../19-logs/logs.md](../19-logs/logs.md) — daemon log
- [../part-i/03-keeping-it-running/the-daily-round.md](../part-i/03-keeping-it-running/the-daily-round.md) — day-to-day checks
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md) — how work moves through the system

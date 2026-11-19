---
title: logs command
commands: [logs]
flags: [--event, --level, --account, --batch, --job, --since, --limit, --follow, --utc, --chain]
concepts: [job, batch]
screens: []
---

# logs (command)

`downcroc logs` reads the daemon’s structured log. Use it to inspect what downcroc did, narrow the record to a specific account, batch, job, or kind of event, and follow new activity as it is written. It is read-only: it never changes daemon state.

For help finding the log file and understanding what events mean, see [logs.md](logs.md) and the [event reference](events/index.md).

## Usage

```text
downcroc logs [--event EVENT] [--level {debug,info,warning,error}]
              [--account ACCOUNT] [--batch BATCH] [--job JOB]
              [--since SINCE] [--limit LIMIT] [--follow] [--addresses] [--utc]
```

With no filters, `logs` prints recent log lines.

## Options

### Filtering

Filters combine to narrow the view. You can apply several at once to home in on a specific situation (for example one job in one batch, or only recent warnings for an account).

`--event EVENT`
: Selects lines whose event name starts with `EVENT`. This is a prefix match, so it picks a family of related events rather than requiring a single exact name. For example, `--event watcher.` matches watcher-related events and `--event job.` matches job-related events. Use this when you know the area of activity you care about.

`--level {debug,info,warning,error}`
: Includes lines at the given severity or higher. For example, `--level warning` shows warnings and errors but omits info and debug lines. Use this to cut through normal activity and focus on problems.

`--account ACCOUNT`
: Filters to lines associated with a specific account id. Useful when diagnosing a single mailbox.

`--batch BATCH`
: Filters to lines associated with a specific [[batch]] id.

`--job JOB`
: Filters to lines associated with a specific [[job]] id. Combine with `--batch` when you want the log for one particular piece of work.

`--since SINCE`
: Sets the start of the time range. Accepts a relative duration such as `15m`, `2h`, or `3d`, or an ISO timestamp. A timestamp without a timezone is read as your computer's local time. Use this to limit the view to recent activity (for example “the last 15 minutes”).

### Amount and streaming

`--limit LIMIT`
: Sets the maximum number of lines to return, from 1 to 5000. Use this to cap output when you only need the most recent or most relevant lines.

`--follow`
: Keeps printing new lines as they are written instead of exiting after the current results. This streams the log continuously until you stop it (for example with Ctrl-C). Use `--follow` when you want to watch what happens live while reproducing or waiting for an event.

### Display

`--chain`
: Renders each event as a thin blue rounded box with level-coloured, wrapped text, and joins consecutive events with a single centred `◆` bead. This is a human-readable view of the same records; use it to follow a sequence of events as one linked chain. It works with `--follow` and `--addresses`. `--json` takes precedence and keeps the raw one-line-per-event output unchanged.

`--addresses`
: Shows account addresses instead of account ids in the output. This can make lines easier to read when you think in terms of mailboxes rather than internal ids.

`--utc`
: Shows timestamps in UTC instead of your computer's local time. Every log line carries both stamps; the display picks local by default, so times match your wall clock. Use this when comparing against server-side records or exporting lines for someone in another timezone.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--addresses`, `--stack`, `--grid`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Output

- **Default:** human-readable lines.
- **`--json`:** machine-readable JSON, one entry per line, suitable for piping to other tools or saving to a file for later inspection.
- **`--follow`:** streams continuously, printing new matching lines as they are appended to the log, until you stop the command.

Because the underlying log is structured (JSONL), `--json` gives you the full structured records without losing fields.

## Examples

- `downcroc logs` — print recent log lines.
- `downcroc logs --level warning --since 15m` — show warnings and errors from the last 15 minutes.
- `downcroc logs --event watcher. --json` — show watcher-related events as JSON (for saving or piping).
- `downcroc logs --addresses --since 15m` — show recent lines with account addresses instead of ids.
- `downcroc logs --batch <batch_id>` — narrow the log to a specific batch.
- `downcroc logs --batch <batch_id> --job <job_id>` — narrow the log to a specific job within a batch.
- `downcroc logs --account <account_id> --level error --since 1h` — show recent errors for one account.
- `downcroc logs --follow` — stream new lines as they are written.
- `downcroc logs --follow --event job. --json` — stream job events live as JSON.
- `downcroc logs --since "2026-11-17 09:00"` — show lines from 9am your local time.
- `downcroc logs --utc --since 1h` — show the last hour in UTC.

## See also

- [logs.md](logs.md) — reading and understanding the daemon log (file location, how to investigate)
- [events/index.md](events/index.md) — meanings of log events and fields
- [../02-status/status.md](../02-status/status.md) — overall health, including the log file path and last write age
- [../10-failed/failed.md](../10-failed/failed.md) — inspect and retry failed jobs
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose the installation and transports

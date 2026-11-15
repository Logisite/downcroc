---
title: Reading and understanding logs
commands: []
flags: []
concepts: [job, batch]
screens: []
---

# Reading and understanding logs

The daemon keeps a structured log of what it does: starting and stopping, locking and unlocking the [[vault]], sending and retrying work, watching mailboxes, and the errors it runs into. When `downcroc status`, `downcroc failed`, or `downcroc doctor` tells you *that* something is wrong but not *why*, the log is where the detail lives.

This page is about how to find and read that log. For the `downcroc logs` command itself (every flag and its behavior), see [command.md](command.md). For what specific events and fields mean, see the [event reference](events/index.md).

## Where the log lives

The daemon writes its log as JSON Lines (one structured record per line) to `downcroc/logs/downcroc.jsonl` under the XDG data directory. On a typical Linux setup this is `~/.local/share/downcroc/logs/downcroc.jsonl` (the exact base depends on your XDG data directory).

To see the exact log file path on this machine and when it was last written, run `downcroc status` — it reports the log file path and its last write age alongside the rest of the system health. `downcroc logs` reads from that same daemon log.

## How to approach a problem

A practical order when something is off:

1. **`downcroc status`** — get the big picture (daemon, vault, sending, accounts, queue, recent failure) and note the log path.
2. **`downcroc failed` / `downcroc doctor` / the relevant command** — identify *what* failed or needs attention (a job, account, transport, batch).
3. **`downcroc logs`** — find *why*, by narrowing to the time, level, and ids involved.

Useful ways to narrow (see [command.md](command.md) for full syntax): `--since 15m` or `--since 2h` to focus on recent activity; `--level warning` (or `error`) to surface problems; `--event watcher.` / `--event job.` (prefix match) to follow a family of events; and `--account`, `--batch`, `--job` to isolate a specific mailbox or piece of work. Use `--follow` to watch events live, and `--json` when you want the full structured records for piping or saving.

## Reading a log record

Each record is structured. In general you will see:

- `ts` — when it happened (UTC).
- `level` — severity (`debug`, `info`, `warning`, `error`, `critical`).
- `event` — the event name (for example `vault.unlocked`, `job.failed`). This is what `--event` matches by prefix.
- `logger` — the component that emitted it.
- Event-specific fields — identifiers and details such as `account`, `batch`, `job`, `reason`, `code`, `detail`, counts, or durations (names depend on the event).

Credential-like fields (passwords, tokens, secrets, authorization material) are redacted before being written. When you need the complete, authoritative fields for a specific line, inspect it as JSON (`downcroc logs --json` or the log file).

## What events mean

The same log stream records many kinds of activity. To understand a specific event and its fields, use the [event reference](events/index.md), which groups events by topic (and is verified against the code that emits them):

- [events/vault.md](events/vault.md) — vault create/unlock/lock and unlock failures.
- [events/service-holds.md](events/service-holds.md) — service pause/resume, holds, dispatch capacity and connectivity.
- [events/jobs-dispatch.md](events/jobs-dispatch.md) — sending, leasing, retries, and batch completion.
- [events/failures.md](events/failures.md) — job failures and retry/forget/reconcile/purge.
- [events/accounts-auth.md](events/accounts-auth.md) — accounts, login/auth, and provider/OAuth issues.
- [events/inbound-watcher.md](events/inbound-watcher.md) — mailbox watching, sync, and inbound source selection.
- [events/policy-config.md](events/policy-config.md) — send policy and configuration changes.
- [events/system.md](events/system.md) — backup/restore, API/SSE, quota, snapshots, and other operational events.

## See also

- [command.md](command.md) — `downcroc logs` flags and examples
- [events/index.md](events/index.md) — meanings of log events and fields
- [../02-status/status.md](../02-status/status.md) — overall health, including the log file path and last write age
- [../../part-i/03-keeping-it-running/problems-list.md](../../part-i/03-keeping-it-running/problems-list.md) — reading problems in order (status, failed, doctor, log)
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose the installation and transports
- [../10-failed/failed.md](../10-failed/failed.md) — inspect and retry failed jobs
- [../09-job/job.md](../09-job/job.md) — inspect a specific job
- [../../part-iii/30-pipeline.md](../../part-iii/30-pipeline.md) — how work moves through the system
- [../../part-iii/33-states.md](../../part-iii/33-states.md) — job, batch, and account states
- [../../part-iii/36-troubleshooting.md](../../part-iii/36-troubleshooting.md) — common problems and where to look

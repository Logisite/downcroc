---
title: Log event reference
commands: []
flags: []
concepts: [job, batch]
screens: []
---

# Log event reference

This reference explains the meanings of log events and their fields as emitted by downcroc (verified against the emitting code). Use it together with [../logs.md](../logs.md) (how to find and read the log) and [../command.md](../command.md) (the `downcroc logs` command).

## How to read a record

Each daemon log line is a structured record (JSON Lines). Common fields:

- `ts` — timestamp (UTC, ISO 8601 with milliseconds).
- `level` — `debug`, `info`, `warning`, `error`, or `critical`.
- `event` — the event name (for example `vault.unlocked`, `job.failed`). `downcroc logs --event` matches this by **prefix**, so `--event job.` selects the `job.*` family.
- `logger` — the component that emitted the record.
- Bound/context fields — operations may bind identifiers (such as request/correlation context) shared across related lines.
- Event-specific fields — ids and details attached by the emitter (commonly `account`, `batch`, `job`, `reason`, `code`, `detail`, counts, durations). You can filter with `--account`, `--batch`, and `--job` when those fields are present.

Credential-like fields (passwords, tokens, secrets, authorization material) are redacted (replaced with `[redacted]`) before being written. Field presence can vary by situation; for the authoritative, complete fields on a specific line, inspect it as JSON (`downcroc logs --json` or the log file shown by `downcroc status`).

## Events by topic

- [vault.md](vault.md) — vault create, unlock, lock, and vault errors.
- [service-holds.md](service-holds.md) — service-level pause/resume, holds, dispatch capacity and connectivity.
- [jobs-dispatch.md](jobs-dispatch.md) — leasing, sending/dispatch, retries, and batch completion.
- [failures.md](failures.md) — job failures and retry/forget/reconcile/purge of failed jobs.
- [accounts-auth.md](accounts-auth.md) — account lifecycle, login/auth, and provider/OAuth events.
- [inbound-watcher.md](inbound-watcher.md) — mailbox watching, sync, sweeps, and inbound source selection.
- [policy-config.md](policy-config.md) — send policy and configuration changes.
- [system.md](system.md) — backup/restore, API/SSE, quota, snapshots, and other operational events.
- [backfill.md](backfill.md) — Gmail thread id backfill lifecycle, lookups, and retries.

## Notes

- A single situation can emit more than one record (and some actions emit both a log line and a published/bus event); the modules note this where relevant.
- Meanings and key fields below are taken from the emitting code (for example `core/vault/*`, `core/holds.py`, `core/dispatch/*`, `core/inbound/*`, `core/accounts/*`, `core/policy/*`, `backup/*`, `api/routes/events.py`). When in doubt, the JSON record is authoritative.

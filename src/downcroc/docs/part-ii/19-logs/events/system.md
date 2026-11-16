---
title: System and operational log events
commands: []
flags: []
concepts: []
screens: []
---

# System and operational log events

Other operational events: backup/restore, API/SSE, quotas, snapshots, input handling, reconciliation, and related diagnostics. Emitters are spread across modules (e.g. `backup/*`, `api/routes/events.py`, `core/bootstrap/foundation.py`, `core/batches/service.py`, `core/dispatch/service.py`, `mail/smtp/session.py`, and others); consult the cited record/emitter for exact fields.

## Backup and restore

- `backup.verified` (**info**) — a backup was verified successfully.
  - `files`: number of files verified.
  - `ok`: verification result (true on success).

- `backup.verify_failed` (**warning**) — backup verification failed.
  - `file`: the file/path that failed verification (as applicable).

- `restore.resumed` (**info**) — a restore operation resumed or completed a step.
  - `marker`: restore marker/progress identifier (as applicable).

## API / SSE

- `sse.connected` (**info**) — an SSE client connected to the event stream.
  - `client`: client identifier/description.
  - `last_event_id`: last event id supplied by the client (if any).

- `sse.disconnected` (**info**) — an SSE client disconnected.
  - `reason`: disconnect reason.

## Quota, snapshots, input, reconciliation

- `quota.reservations_reset` (**info**) — stale quota reservations were reset (for example at startup).
  - `count`: number reset.

- `send_attempts.reconciled` (**warning**) — send attempts/state were reconciled (corrected) on startup or recovery.
  - `count`: number of attempts reconciled.

- `snapshot.stored` (**info**) — an input snapshot was stored.
  - `hash`: content hash.
  - `bytes`: size in bytes.

- `input.field_ignored` (**info**) — an input field was ignored during processing.
  - `key`: the input/item key.
  - `field`: the ignored field name.

## Miscellaneous diagnostics

- `smtp.sessions_verified` (**info**) — SMTP session verification ran.
  - Includes counts such as `kept` and `dropped` as emitted.

- `daemon.start_failed` (**error**) — the daemon failed to start (e.g. from service/runtime start path).
  - `reason`: failure reason (`db_migration_failed`, `bootstrap_failed`, or another startup reason).
  - `detail`: a short description of the failure.
  - `hint`: the next action when one is available.
  - `error`, `traceback`: when `reason=bootstrap_failed`, the error class and a truncated traceback.

- `event.gap` (**warning**) — indicates a gap in event sequencing/stream where detected (e.g. requested event id older than available history).
  - `requested_id`: the id requested by the client.
  - `oldest_id`: the oldest available id (or `null`/absent if none).

- `thread.broken` and similar diagnostics — emitted when an invariant or unexpected threading condition is detected, with fields describing the condition (see the record).

This module is not exhaustive of every rare/internal diagnostic; for any event not listed here, read the JSON record (`downcroc logs --json`) and trace the `event` name to its emitter in the codebase.

## Daemon and database lifecycle

- `daemon.start` (**info**) — the daemon process is starting (detached/startup path).
  - Typically includes service/daemon context such as pid/url/host/port as emitted by the startup path.

- `daemon.ready` (**info**) — the HTTP daemon finished startup and is ready to serve.
  - `port`: the API port.
  - `boot_ms`: startup time in milliseconds.

- `daemon.stopping` (**info**, when emitted) — the daemon is shutting down.
  - Fields as emitted for the shutdown path.

- `daemon.recovered` (**info/warning**, when emitted) — the daemon recovered from a prior abnormal state on startup.
  - Fields as emitted.

- `db.revision_ok` (**info**) — the recorded database revision is known to this build and startup may proceed.
  - `current`: the recorded revision (or `none`).
  - `head`: the newest migration revision in this build.
  - `known_revisions`: number of revisions available in this build.

- `db.migrate_failed` (**error**) — the recorded database revision is not in this build, or a migration failed. Emitted as one short structured event instead of a raw traceback; the daemon then exits with a short message.
  - `reason`: `unknown_revision` (database newer than the installed code) or `upgrade_failed`.
  - `current`: the recorded revision (or `none`).
  - `head`: the newest migration revision in this build.
  - `known_revisions`: when `reason=unknown_revision`, the sorted list of known revisions.
  - `error`, `detail`: when `reason=upgrade_failed`, the error class and a truncated detail.
  - `hint`: the next action, for example install a newer release or restore a backup.

- `db.migrate` (**info**) — database migrations were applied on startup.
  - `from`: previous schema revision (or `none`).
  - `to`: target/head revision (or `none`).
  - `duration_ms`: migration duration in milliseconds.

## OpenAPI, backup, and restore

- `openapi.exported` (**info**) — the OpenAPI document was exported.
  - `path`: destination path (or `stdout`).
  - `routes`: number of API routes/paths in the document.

- `backup.created` (**info**) — a backup bundle was created.
  - Typically includes bundle path, file/byte counts, duration, and schema/count details as emitted.

- `restore.staged` (**info**) — a restore bundle was staged/applied during a restore.
  - `bundle`: bundle path (and related fields as emitted).

- `restore.swapped` (**info**) — restored data was swapped into place.
  - Includes restored counts/revision and previous-data details as emitted.

- `restore.refused` (**warning/error**) — a restore was refused (e.g. invalid/incompatible bundle).
  - `bundle`/`revision`/`current`/`reason` as emitted for the refusal.

## Quota

- `quota.reservations_reset` (**info**) — stale send quota reservations were reset on startup.
  - `count`: number of reservations reset.

- `quota.reserved` (**info**, when emitted) — quota was reserved for sending.
  - Fields such as account/day/amount as emitted.

- `quota.released` (**info**, when emitted) — reserved quota was released.
  - Fields as emitted.

- `quota.committed` (**info**, when emitted) — reserved quota was committed after a send.
  - Fields as emitted.

- `quota.exhausted` (**info/warning**, when emitted) — an account’s quota/allowance is exhausted.
  - Fields as emitted.

- `quota.reserve_failed` (**warning/error**, when emitted) — reserving quota failed.
  - Fields as emitted.

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../20-backup/backup.md](../../20-backup/backup.md) — backup commands
- [../../21-restore/restore.md](../../21-restore/restore.md) — restore commands
- [../../23-openapi/openapi.md](../../23-openapi/openapi.md) — API/OpenAPI
- [../../02-status/status.md](../../02-status/status.md) — overall health

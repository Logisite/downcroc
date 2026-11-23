---
title: Extension log events
commands: []
flags: []
concepts: []
screens: []
---

# Extension log events

This reference explains the events the extension host writes to the daemon log.
It is the record of what an extension was allowed to do, what it actually did,
and when the host had to stop or restart it. The
[extension command](../../28-extension/extension.md) explains how to manage
extensions; this page explains what you read back afterwards.

Every event in this family carries `extension`, the extension id from its
manifest. That is the thread that ties all of them together. When you run
`downcroc extension logs ID`, the command filters for this id for you. When you
read the raw JSONL log, this is the field you filter on yourself.

No event in this family carries a password, token, vault path, or secret value.
That is not a formatting choice. The extension never receives a credential, so
there is nothing to log by accident.

## Lifecycle

- `extension.started` (**info**) — the daemon started an enabled extension.
  - `extension`: extension id from the manifest.
  - `mode`: `subprocess` or `inprocess`. Subprocess is the default; in-process
    requires `trust = true`.

- `extension.stopped` (**info**) — the host stopped an extension.
  - `extension`: extension id.
  - `reason`: why it stopped, usually `disabled` or `shutdown`.

- `extension.crashed` (**error**) — the process exited or could not be started.
  - `extension`: extension id.
  - `error`: error class.
  - `detail`: short detail. The host restarts up to `extensions.max_restarts`.

- `extension.timeout` (**error**) — the extension did not answer an event in
  time.
  - `extension`: extension id.
  - `error`: error class.
  - `detail`: short detail. The same restart ceiling applies.

## Log events and bus events

This whole family is log only. An `extension.*` event is written to the JSONL
log and is readable with `downcroc logs --event extension.` or
`downcroc extension logs ID`. It is not published to the daemon event bus, so it
does not appear in the `/api/events` stream unless an extension explicitly
calls the elevated `event.publish` capability with that name.

That distinction matters for other families too. `quota.committed` is written
to the log **and** published to the bus, along with events such as
`policy.changed`, `vault.unlocked`, `vault.locked`, `batch.approved`, and
`job.sent`. Most other log lines are diagnostics only. When an extension needs
an event, subscribe by the daemon event name, not by the log line name. The
payload fields an extension receives are documented in
[Wire protocol](../../28-extension/protocol.md).

## Approval

- `extension.approved` (**info**) — an elevated extension was approved with the
  vault password.
  - `extension`: extension id.
  - `tier`: `elevated`.
  - `manifest_digest`: short prefix of the approved manifest digest.

- `extension.revoked` (**info**) — elevated approval was removed.
  - `extension`: extension id.

## Artifact verification

- `extension.artifact_invalid` (**error**) — a packaged extension artifact was
  missing or its checksum did not match.
  - `extension`: extension id.
  - `detail`: short reason. No extension code is run after this event.

## Capability calls

- `extension.call` (**info**) — a capability call completed successfully.
  - `extension`: extension id.
  - `capability`: capability name.
  - `outcome`: `ok`.
  - `duration_ms`: time the broker spent on the call.

- `extension.denied` (**info**) — a capability call was refused.
  - `extension`: extension id.
  - `capability`: capability name.
  - `outcome`: `error`.
  - `duration_ms`: call duration.
  - `error`: error class.
  - `detail`: short reason, usually a missing grant or an unlisted host.

- `extension.call_failed` (**info**) — a granted capability failed while
  running.
  - `extension`: extension id.
  - `capability`: capability name.
  - `outcome`: `error`.
  - `duration_ms`: call duration.
  - `error`: error class.
  - `detail`: short reason.

## Notifications

- `extension.notify` (**info**) — an extension asked the host to emit a
  notification.
  - `extension`: extension id.
  - `message`: short message supplied by the extension. This is an audit
    record, not a desktop popup.

## Reading these events in context

Start with the extension id, then read forward in time. A healthy run is
`extension.started`, then one or more `extension.call` events, then
`extension.stopped` when you disable it. A restart shows up as a crash or
timeout followed by another start.

When a capability is missing from the log, the extension either was not
subscribed to the event or did not ask for the call. Check the manifest's
`events` list and the config's `allow` list before looking deeper.

## See also

- [../../28-extension/extension.md](../../28-extension/extension.md) — managing extensions
- [../../part-iii/38-config.md](../../part-iii/38-config.md) — host settings
- [../logs.md](../logs.md) — reading the daemon log

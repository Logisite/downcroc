---
title: Extension capabilities
commands: []
flags: []
concepts: []
screens: []
---

# Extension capabilities

Every capability is default deny. An extension may call only what its manifest
declares and your config grants. Elevated capabilities also require approval.
Use `downcroc extension capabilities --json` to see what this build supports and
which tier each capability belongs to.

The call shape is always the same:

```json
{"capability": "NAME", "params": {"key": "value"}}
```

The result shape is always:

```json
{"ok": true, "value": ...}
```

or:

```json
{"ok": false, "error": "ERROR", "detail": "short reason"}
```

## State and logging

### kv.get

Tier: standard. Reads one key from this extension's private store.

```json
{"capability": "kv.get", "params": {"key": "handled:msg_1"}}
```

The value is a string, or `null` when the key is absent. One extension cannot
read another extension's keys.

### kv.set

Tier: standard. Writes one key. Values are stored as strings.

```json
{"capability": "kv.set", "params": {"key": "handled:msg_1", "value": "1"}}
```

### kv.delete

Tier: standard. Removes one key.

```json
{"capability": "kv.delete", "params": {"key": "handled:msg_1"}}
```

### kv.list

Tier: standard. Returns all keys and values for this extension.

```json
{"capability": "kv.list", "params": {}}
```

### log

Tier: standard. Writes a structured log line with your extension id.

```json
{"capability": "log", "params": {"level": "info", "message": "seen", "fields": {"source": "reply"}}}
```

Levels are `debug`, `info`, `warning`, and `error`. The `fields` object is
optional and its values are strings. Never put a credential in a log field.

## Inspection

### message.get

Tier: standard. Returns one inbound message by id.

```json
{"capability": "message.get", "params": {"message": "msg_1"}}
```

### message.list and message.search

Tier: standard. Return messages with optional filters `account`, `thread`,
`reply_state`, `since`, `until`, `limit`, `offset`, and `newest_first`.

```json
{"capability": "message.search", "params": {"account": "acct_1", "reply_state": "confirmed", "limit": 20}}
```

### thread.get and thread.list

Tier: standard. `thread.get` takes `thread`. `thread.list` accepts `account`,
`batch`, `limit`, and `offset`.

```json
{"capability": "thread.get", "params": {"thread": "thr_1"}}
```

### job.get, job.list, job.attempts

Tier: standard. `job.get` and `job.attempts` take `job`. `job.list` accepts
`batch`, `account`, `state`, `limit`, `offset`, and `newest_first`.

```json
{"capability": "job.attempts", "params": {"job": "job_1"}}
```

### batch.get, batch.list, batch.followups, batch.suppression

Tier: standard. The single-batch calls take `batch`. `batch.list` accepts
`state`, `limit`, and `offset`.

```json
{"capability": "batch.followups", "params": {"batch": "bat_1"}}
```

### stats.query

Tier: standard. Accepts `kind` (`summary`, `hourly`, `daily`, `accounts`,
`batches`), `from`, `to`, and `account`.

```json
{"capability": "stats.query", "params": {"kind": "daily", "from": "2026-11-01"}}
```

### logs.query

Tier: standard. Accepts `event` as a prefix and `limit`.

```json
{"capability": "logs.query", "params": {"event": "reply.", "limit": 100}}
```

### config.get and config.schema

Tier: standard. `config.get` returns the effective config snapshot without
secrets. `config.schema` lists fields and constraints.

```json
{"capability": "config.get", "params": {}}
```

### account.list, account.get, account.audit

Tier: standard. `account.get` and `account.audit` take `account`. No credential
is returned by any of them.

```json
{"capability": "account.list", "params": {}}
```

### transport.list, transport.get, transport.history

Tier: standard. `transport.get` takes `account` and `transport`. The list call
takes `account`.

```json
{"capability": "transport.list", "params": {"account": "acct_1"}}
```

### provider.list, provider.get, provider.declaration

Tier: standard. Provider declarations are public metadata.

```json
{"capability": "provider.list", "params": {}}
```

### doctor.capacity, service.status, service.health

Tier: standard. These are read-only views of dispatch and service state.

```json
{"capability": "doctor.capacity", "params": {}}
```

### followup.status, followup.outlook, followup.due

Tier: standard. `followup.status` takes `batch`. The other two accept `due`.

```json
{"capability": "followup.outlook", "params": {"due": "7d"}}
```

### capability.list

Tier: standard. Returns every capability name with its tier.

```json
{"capability": "capability.list", "params": {}}
```

## Mail

### mail.reply

Tier: standard. Replies to an inbound message using the same account and the
existing threading machinery.

```json
{"capability": "mail.reply", "params": {"message": "msg_1", "text": "Thanks, noted."}}
```

Optional parameters are `subject`, `cc`, and `html`. The result contains `job`,
`message_id`, and `in_reply_to`. The reply is recorded as sent by your
extension and does not re-trigger the hook that caused it.

### mail.send

Tier: standard. Sends a new message from a named account.

```json
{"capability": "mail.send", "params": {"account": "acct_1", "to": "person@example.com", "subject": "Hello", "text": "Hi"}}
```

The result contains `job` and `message_id`.

### mail.forward

Tier: standard. Like `mail.reply` but prefixes the subject with `Fwd:` and
includes the original subject in the body.

```json
{"capability": "mail.forward", "params": {"message": "msg_1", "text": "Sharing this."}}
```

### mail.sync

Tier: standard. Asks an account to sync now. Takes `account`.

```json
{"capability": "mail.sync", "params": {"account": "acct_1"}}
```

### mail.prune

Tier: standard. Runs retention pruning. Returns the pruning summary.

```json
{"capability": "mail.prune", "params": {}}
```

### Remote mailbox actions

`mail.fetch`, `mail.mark_read`, `mail.mark_unread`, `mail.flag`, `mail.move`,
`mail.delete`, `mail.classify`, and `mail.attribute_reply` are registered
standard capabilities. Their current handlers validate and log the request but
do not yet change remote mailbox state. Do not rely on their side effects.

## Jobs and batches

### job.create, job.send, job.cancel, job.retry

Tier: standard. `job.send` takes `job`. `job.cancel` and `job.retry` take `job`.
`job.create` takes `account`, `to`, `subject`, `text`, and optional `batch`,
`to_name`, and `html`.

```json
{"capability": "job.create", "params": {"account": "acct_1", "to": "person@example.com", "subject": "Hi", "text": "Hello"}}
```

### batch.submit, batch.validate, batch.preview

Tier: standard. These take `path` and optional `key`.

```json
{"capability": "batch.validate", "params": {"path": "/tmp/campaign.json"}}
```

### batch.approve, batch.cancel, batch.pause, batch.resume, batch.delete

Tier: standard. These take `batch`. `batch.approve` also accepts `mode`, either
`one` or `all`.

```json
{"capability": "batch.approve", "params": {"batch": "bat_1", "mode": "all"}}
```

### followup.declare, followup.remove, followup.retire

Tier: standard. `followup.declare` takes `batch`, `step`, and `path`, with
optional `kind`, `version`, and `dry_run`. The other two take `batch` and
`step`.

```json
{"capability": "followup.retire", "params": {"batch": "bat_1", "step": "bump-1"}}
```

### followup.plan_due and followup.cancel

Tier: standard. These take no required parameters.

```json
{"capability": "followup.plan_due", "params": {}}
```

## Elevated capabilities

These require `tier = "elevated"` in the manifest and an approval with the
vault password. They are described fully in [Elevated extensions](elevated.md).
They include `http.request`, `cli.run`, `notify`, `config.set`, `policy.set`,
`policy.clear`, `vault.lock`, `vault.unlock`, `secret.put`, `secret.delete`,
`key.rotate`, transport and provider changes, service and daemon control,
backup and restore, import and export, database maintenance, timers, and
command registration.

## Denials

A capability can fail for three reasons:

- it is not in your manifest or not granted in config
- it is elevated and the extension is not approved
- the action parameters are missing or invalid

All three return `ok: false` with a short `detail`. The daemon also logs
`extension.denied` for grant and tier failures, and `extension.call_failed` for
runtime errors. The extension keeps running after a denial.

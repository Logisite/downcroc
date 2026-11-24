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

### quota.get

Tier: standard. Returns the current quota snapshot for an account. It takes
`account`.

```json
{"capability": "quota.get", "params": {"account": "acct_1"}}
```

The result contains `account`, `day`, `limit`, `used`, `reserved`, and
`remaining`. `remaining` is `max(0, limit - used - reserved)`. No extension
credential is returned. For a fleet view, call `stats.query` with
`kind = "accounts"`, which returns `used`, `reserved`, and `available` per
account.

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

## Complete capability index

The sections above give full examples for the capabilities you will use most.
This index documents every registered capability so you can check grants, tiers,
and call shapes without reading source. The `downcroc extension capabilities
--json` command returns the same names with their tiers.

### account.create, account.connect, account.disconnect

Tier: standard. `account.create` takes `provider`, `address`, and optional
`label`. `account.connect` takes `account` and starts a connection attempt.
`account.disconnect` takes `account` and refreshes its state.

```json
{"capability": "account.connect", "params": {"account": "acct_1"}}
```

### account.pause, account.resume

Tier: standard. Take `account` and an optional `reason`. Pausing holds sending
for that account; resuming releases the hold.

```json
{"capability": "account.pause", "params": {"account": "acct_1", "reason": "maintenance"}}
```

### account.archive, account.unarchive, account.reassign

Tier: standard. All take `account`. `account.reassign` also takes `to` and
optional `job_ids`. Archiving hides the account from normal lists; unarchiving
restores it.

```json
{"capability": "account.archive", "params": {"account": "acct_1"}}
```

### account.delete, account.rename, account.set_credentials

Tier: elevated. All take `account`. Deletion is a destructive operation.
Renaming changes the label. Setting credentials writes through the vault and
never returns the credential. These require approval.

```json
{"capability": "account.rename", "params": {"account": "acct_1", "name": "Work mail"}}
```

### backfill.status, backfill.start, backfill.stop, backfill.scan, backfill.resolve

Tier: standard for `backfill.status`, elevated for the other four. Status is a
read-only view. Start and stop control the worker. Scan and resolve trigger a
thread-id lookup. No credential is returned.

```json
{"capability": "backfill.status", "params": {}}
```

### backup.create, backup.list, backup.restore, export.json, import.json

Tier: elevated. These manage portability artifacts. `backup.create` takes an
optional `include_logs`. `backup.restore` takes `bundle`. Import and export
take a `path`. They require approval.

```json
{"capability": "backup.list", "params": {}}
```

### batch.thread, batch.reassign

Tier: standard for `batch.thread`, elevated for `batch.reassign`. The thread
call takes `batch`; reassign takes `batch` and `to`.

```json
{"capability": "batch.thread", "params": {"batch": "bat_1"}}
```

### events.query, event.publish

Tier: standard for `events.query`, elevated for `event.publish`. Query accepts
`prefix` and `limit`. Publish takes `event` and `payload`. A published event
goes to the daemon event bus; it does not write a log line by itself.

```json
{"capability": "events.query", "params": {"prefix": "reply.", "limit": 50}}
```

### failed.list, failed.get

Tier: standard. `failed.list` accepts `limit` and `offset`. `failed.get` takes
`failure`. No retry action is exposed here; use `job.retry` with the job id.

```json
{"capability": "failed.list", "params": {"limit": 20}}
```

### holds.list, hold.set, hold.clear, quota.reserve, quota.release, quota.set

Tier: standard for `holds.list`, elevated for the rest. `holds.list` is a
read-only view. The others take `target`, which is `service`, `account`,
`batch`, or `job`, plus the matching id and optional `reason`. Quota calls take
`account`, `day`, and a count or limit. They require approval.

```json
{"capability": "holds.list", "params": {}}
```

### job.artifacts, job.claim, job.release, job.pause, job.resume, job.reassign, job.unpin

Tier: standard for `job.artifacts`, `job.pause`, `job.resume`, and `job.unpin`;
elevated for `job.claim`, `job.release`, and `job.reassign`. The single-job
calls take `job`. Reassign also takes `to`. Claim and release are runtime
operations and require approval.

```json
{"capability": "job.pause", "params": {"job": "job_1", "reason": "review"}}
```

### mail.fetch, mail.mark_read, mail.mark_unread, mail.flag, mail.move, mail.delete, mail.classify, mail.attribute_reply

Tier: standard. These are registered and validated, and their calls are logged,
but their current handlers do not change remote mailbox state. Do not rely on
their side effects. Use `mail.reply` and `mail.send` for real sends.

```json
{"capability": "mail.mark_read", "params": {"message": "msg_1"}}
```

### policy.get, policy.effective, policy.set, policy.clear

Tier: standard for the two read calls, elevated for the two writes. Read calls
take `account`. Writes take `account` or no account for global scope, plus a
`values` object. Writes require approval.

```json
{"capability": "policy.get", "params": {"account": "acct_1"}}
```

### provider.install_declaration, provider.set_override, provider.call

Tier: elevated. These change provider declarations or call a provider-specific
operation. They take `provider` and optional `values` or call arguments. They
require approval.

```json
{"capability": "provider.call", "params": {"provider": "gmail", "operation": "list"}}
```

### secret.list, secret.exists, secret.put, secret.delete, key.rotate, vault.lock, vault.unlock, vault.status

Tier: standard for `secret.list`, `secret.exists`, and `vault.status`; elevated
for the rest. Secret calls take `key`, and `secret.put` also takes `value`. No
call returns a secret value. `vault.unlock` takes `password`, which is redacted
from every log and event. Key rotation and vault control require approval.

```json
{"capability": "secret.exists", "params": {"key": "acct_1:refresh_token"}}
```

### service.pause, service.resume, daemon.restart, daemon.stop

Tier: elevated. These control the daemon and require approval. Pause and resume
take an optional `reason`. Restart and stop are registered control points.

```json
{"capability": "service.pause", "params": {"reason": "maintenance"}}
```

### stats.rebuild, stats.prune, db.vacuum, db.integrity_check

Tier: elevated. These are maintenance operations. `stats.rebuild` takes an
optional `since`. They require approval.

```json
{"capability": "stats.rebuild", "params": {"since": "7d"}}
```

### suppression.add, suppression.remove, suppression.clear

Tier: standard. Add and remove take `account` and `address`. Clear takes
`account`. These change which addresses are skipped by follow-ups.

```json
{"capability": "suppression.add", "params": {"account": "acct_1", "address": "person@example.com"}}
```

### thread.timeline

Tier: standard. Takes `thread` and returns the ordered messages and sends in
that thread.

```json
{"capability": "thread.timeline", "params": {"thread": "thr_1"}}
```

### timer.schedule, timer.cancel, command.register, cli.run, notify, notify.system

Tier: elevated. These extend runtime behavior and require approval.
`timer.schedule` takes `name` and `after_s`; `timer.cancel` takes `name`.
`command.register` takes a command descriptor. `cli.run` takes `argv`, a list
of CLI arguments. `notify` takes `message` and records a log event.
`notify.system` takes `title` and `message` and calls the configured notifier
command with those two arguments appended. No shell is used. If no notifier is
configured, it returns `ok: false` with `error: notify_unavailable`.

```json
{"capability": "cli.run", "params": {"argv": ["status", "--json"]}}
```

```json
{"capability": "notify.system", "params": {"title": "Quota", "message": "Allowance exhausted"}}
```

### config.set, update.check, update.install, update.status

Tier: elevated for `config.set` and `update.install`, standard for
`update.check` and `update.status`. `config.set` takes a `patch` object.
Update calls take no required parameters.

```json
{"capability": "update.check", "params": {}}
```

### transport.add, transport.update, transport.remove, transport.enable, transport.disable, transport.test, transport.set_priority, transport.clear_cooldown, transport.forget_health

Tier: elevated. All take `account` and `transport` except `transport.add`,
which also takes `kind`. These change transport state and require approval.
No credential is returned.

```json
{"capability": "transport.set_priority", "params": {"account": "acct_1", "transport": "trn_1", "priority": 10}}
```

### dispatch.pause, dispatch.resume

Tier: elevated. These pause or resume the dispatcher and take an optional
`reason`. They require approval.

```json
{"capability": "dispatch.pause", "params": {"reason": "maintenance"}}
```

### http.request, socket.connect

Tier: elevated. `http.request` takes `url`, optional `method`, `headers`,
`body`, and `credential`. The host must be granted or wildcarded.
`socket.connect` is registered but is not available in this release; it is
denied before any connection is made. Both require approval.

```json
{"capability": "http.request", "params": {"url": "https://api.example.com/me", "credential": "account:acct_1"}}
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

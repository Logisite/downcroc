---
title: Extension troubleshooting
commands: []
flags: []
concepts: []
screens: []
---

# Extension troubleshooting

This page covers the failures you can see from the CLI and the daemon log. It
does not require reading source.

## Start here

```sh
downcroc extension list
downcroc extension logs <id> --json
```

`list` tells you whether the extension is discovered, enabled, and running.
`logs` shows only events for that extension and is the fastest way to see what
the daemon thought happened.

## The extension does not appear

Check that the manifest is in `~/.config/downcroc/extensions` and ends in
`.toml`. Run `downcroc extension reload`, then `list` again. A bad manifest is
refused with `extension_manifest_invalid`. The error names the file and field.

If you installed a `.pyz`, the derived manifest is written next to the archive.
Deleting that manifest removes the extension from `list`.

## The extension does not start

Look for `extension.crashed` or `extension.timeout` in the log.

`extension.crashed` means the process exited or could not be started. Check
that `run` points at a real executable for a local manifest, or that the `.pyz`
still exists and verifies with `extension verify`.

`extension.timeout` means the process did not answer with an actions frame in
`extensions.call_timeout_s`. The usual cause is a program that prints non-JSON,
forgets `flush=True`, or blocks before reading its first line.

The host restarts a failed extension up to `extensions.max_restarts`. After
that it stays stopped.

## A capability is denied

Look at the action result first:

```json
{"ok": false, "error": "CapabilityDenied", "detail": "capability not granted"}
```

Then check three things in order:

1. The manifest declares the capability.
2. `[extensions.<id>].allow` in config grants it.
3. If it is elevated, the extension is approved.

The daemon also logs `extension.denied` with the extension id, capability, and
reason. A denial is not a crash. The extension keeps running.

## "capability needs tier = elevated"

The manifest requests an elevated capability while `tier = "standard"`. Change
the manifest to `tier = "elevated"`, rebuild or reinstall, reload, then approve
the extension with `downcroc extension approve <id>`.

## "capability needs an approved extension"

The manifest is elevated but no valid approval exists. Approve it. If you
already approved it, the manifest or artifact changed since approval. Reload
and approve again.

Use `downcroc extension approval <id> --json` to see the current state.

## Approval says the password is wrong

The approval password is the vault password. If the vault has not been
initialized, initialize it first. If you changed the vault password, use the
current one. Repeated wrong passwords trigger the same throttle as vault
unlock. Wait for the retry time shown in the error.

## The vault is locked

Approval still works. The approval command uses the password to unlock the
vault and approve in one step. After approval, capability calls that need
secrets fail with `vault_locked` until you run `downcroc vault unlock`. Calls
that do not need secrets keep working.

## "artifact invalid"

The installed `.pyz` is missing or its checksum no longer matches. Reinstall it
with `downcroc extension add FILE.pyz`. If you intentionally built a new
version, approve the extension again because the manifest digest changed.

## No events arrive

Check the manifest `events` list. Use real daemon event names. For replies, the
event is `reply.attributed`, not `reply.received`. You can discover names with:

```sh
downcroc logs --event
```

An extension only receives events it subscribes to. A typo means silence, with
no error.

## The reply is not threaded

`mail.reply` derives threading from the inbound message. Pass the real message
id from the event payload, not a job id or subject. The result contains
`in_reply_to` so you can confirm which job was used.

If the inbound message was never attributed to a job, threading falls back to
the available headers. The reply still sends, but the thread link may be weaker.

## Duplicate replies

Use `kv.get` and `kv.set` with a key derived from the message id before calling
`mail.reply`. Check the result of `kv.get` and skip when the key exists. The
daemon also prevents your own send from re-triggering the same hook, so the two
mechanisms together stop loops.

## The CLI run result is empty

`cli.run` returns `returncode`, `stdout`, and `stderr`. Check `returncode` first.
A nonzero code means the CLI command failed. Output is truncated at 8000
characters per stream and the bearer token is replaced with `[redacted]`.

## Where to look next

- [Writing an extension](authoring.md)
- [Wire protocol](protocol.md)
- [Capabilities](capabilities.md)
- [Elevated extensions](elevated.md)
- [Artifacts](artifacts.md)
- [Extension log events](../19-logs/events/extensions.md)

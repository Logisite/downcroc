---
title: extension
commands: [extension, extension.list, extension.show, extension.add, extension.enable, extension.disable, extension.reload, extension.logs, extension.capabilities, extension.test, extension.run]
flags: ["extension.logs --follow", "extension.test --input"]
concepts: []
screens: []
---

# extension

`extension` is where you bring other people's behavior into downcroc without
changing the daemon. You reach for it when a script or an agent needs to react
to something downcroc knows, such as a reply arriving, and needs to do
something credentialed in return, such as answer that reply. The idea behind it
is simple: the extension asks, and the daemon does. The daemon keeps the
credentials, the database, and the send path. The extension only sees events
and receives results.

Extensions are separate programs. The daemon starts them as child processes and
speaks JSON lines to them. That boundary is what keeps a third-party extension
away from your vault. A Python script is the usual choice, but the protocol is
plain text, so another language works too.

The event names in a manifest are real daemon event names. For reply work the
one you usually want is `reply.attributed`, which is written when an incoming
message has been tied to a send and a thread. `reply.unattributed` is written
when that link could not be made. Other useful events include `job.sent`,
`message.ingested`, and `batch.done`. Use `downcroc logs --event` to explore the
family you want before you subscribe to it.

```text
downcroc extension
├── list
├── show      EXTENSION
├── add       PATH
├── build     DIR [--output PATH]
├── verify    EXTENSION
├── approval  EXTENSION
├── approve   EXTENSION [--password PASSWORD]
├── revoke    EXTENSION
├── enable    EXTENSION
├── disable   EXTENSION
├── reload
├── logs      EXTENSION [--follow]
├── capabilities
├── test      EXTENSION --input JSON [--rounds N]
├── inject    EXTENSION --event NAME [--payload JSON]
└── run       EXTENSION COMMAND [ARGS...]
```

## Finding out what is installed

`list` answers the question "what is here right now?". It reads the manifests
from disk, compares them with the running processes, and tells you whether each
extension is enabled and running.

```text
downcroc extension list [--json]
```

The rows show the id, name, version, enabled state, running state, and the
events each extension subscribes to. An extension can be enabled but not
running if the daemon has not started it yet, or if its last start failed. Use
`--json` when you want to script around those fields.

`show` is the closer look. It takes one extension id and prints the same
fields for just that extension, including its declared commands and events.

```text
downcroc extension show ID [--json]
```

If the id is not known, the command exits with an error and prints
`extension_not_found` as JSON. That usually means the manifest has not been
added or the daemon has not reloaded since it was added.

`capabilities` answers a different question: what could an extension ask for
at all? It lists every capability the running daemon can broker.

```text
downcroc extension capabilities [--json]
```

Seeing a name here does not mean an extension may use it. Grants live in the
config under `[extensions.<id>]`. Capabilities are default deny.

## Bringing an extension in

`add` copies a manifest into the extensions directory under your config home.
The original file stays where it is. This keeps installing an extension a
single, reversible file copy.

```text
downcroc extension add PATH
```

`PATH` must be a TOML file. If it is not a file, the command reports
`manifest_not_found`. If a file with the same name already exists in the
extensions directory, it is overwritten. The command prints the destination
path so you can see where the manifest landed.

Adding a file does not wake the daemon up. `reload` does that.

```text
downcroc extension reload
```

Reload stops every running extension, re-reads all manifests, re-reads the
extension config, and starts the ones that are enabled. Reach for it after you
add, edit, or remove a manifest. A broken manifest is refused with
`extension_manifest_invalid`, but the other extensions still load, so one bad
file does not take the whole host down.

## Installing a single-file artifact

A `.pyz` artifact is one file containing the extension code and its manifest. It
is the closest thing downcroc has to a VSIX package, without a marketplace. It
is useful when someone sends you an extension and you want one file to check,
copy, and install.

Build one from a directory containing `__main__.py` and
`downcroc-extension.toml`:

```text
downcroc extension build DIR [--output PATH]
```

The command prints the output path and its SHA-256. The checksum is not a
signature. It does not tell you the author is trustworthy. It tells you the file
you install is the same file you checked.

Install the artifact with the same `add` command you use for manifests:

```text
downcroc extension add reply-bot.pyz
```

The installer reads the manifest from the archive, copies the artifact under
your config directory, records the checksum, writes a derived manifest, and
reloads the host. The extension is installed but not enabled. Enable it
separately when you are ready.

`downcroc extension verify ID` recomputes the checksum and reports whether the
artifact still matches. The host also verifies it before every launch. A missing
file or a changed file stops the extension and writes
`extension.artifact_invalid` to the log. No extension code runs in that case.

Checksums protect against accidental or later changes to the file. They do not
sandbox the code, and they do not replace capability grants. The extension still
runs as a child process with only the capabilities you granted.

## Turning an extension on and off

`enable` marks an extension enabled and starts its process immediately if it is
not already running.

```text
downcroc extension enable ID
```

The id must already be known, so add and reload the manifest first. Grants come
from `[extensions.<id>]` in config. If that table has no `allow` list, the
extension receives the capabilities it declared in its manifest.

`disable` stops the process and marks the extension disabled.

```text
downcroc extension disable ID
```

The manifest remains on disk and its persistent state row remembers the
disabled choice. Enabling it again starts the same extension. Disabling is the
right move when an extension misbehaves and you still want to keep its files.

## Reading what an extension did

`logs` reads the daemon's JSONL log and keeps only the events that belong to
one extension.

```text
downcroc extension logs ID [--follow]
```

Without `--follow`, the command reads what has been written and stops. With it,
the command keeps watching and prints new events as they arrive. `--json`
prints the raw entries instead of a table.

The events you will see are `extension.started`, `extension.stopped`,
`extension.crashed`, `extension.timeout`, `extension.call`, `extension.denied`,
`extension.call_failed`, and `extension.notify`. They are explained in
[Extension log events](events.md). No event contains a credential.

## Trying an extension once

`test` is the safe way to see what an extension does before you let it run on
real events. It starts a fresh process, sends one event, executes the actions
that come back, and prints the results.

```text
downcroc extension test ID --input JSON [--rounds N]
```

`--input JSON` is required. The JSON object becomes the event payload. Give it
an `event` field such as `reply.attributed`, and useful ids such as `message`.
The host always sanitizes the payload, so unknown fields are dropped before
the extension sees them.

`--rounds N` allows N action rounds for the one event. The default is 1. Use 2
or more when testing an extension that reads a result and then emits another
action, such as the reply bot in [Writing an extension](authoring.md). A round
ends when the extension sends an empty `actions` list. The host stops at
`extensions.max_protocol_rounds` even if you pass a larger N.

The result is a JSON list with one entry per action in the final round. A
successful entry is the capability result. A refused capability returns
`error: CapabilityDenied` and a short `detail`. The process is stopped after
the test even when an action fails. If the extension does not answer within
`extensions.call_timeout_s`, the result reports a timeout and the host logs
`extension.timeout`.

## Injecting an event

```text
downcroc extension inject ID --event NAME [--payload JSON]
```

`inject` publishes a daemon event through the same bus path the daemon uses.
The named extension must be running and subscribed to that event. The payload
is sanitized like any other event payload.

```sh
downcroc extension inject watcher \
  --event quota.committed \
  --payload '{"account":"acct_1","used":30,"limit":50,"remaining":20,"day":"2026-11-24"}'
```

This is the supported way to test event-driven extensions without waiting for
real mail or quota activity. It works for `extension test` publishers too: an
extension that calls `event.publish` reaches running subscribers through the
same bus.

Use `test` and `inject` after changing a manifest or a grant, because they
exercise the whole path without waiting for real mail.

## Running a contributed command

A manifest can declare commands of its own. When it does, those commands appear
as normal downcroc commands, and `run` is the direct route to the same place.

```text
downcroc extension run ID COMMAND [--NAME VALUE]
```

`ID` is the extension id, and `COMMAND` is one of the names declared in its
manifest. Options are written as `--name value`. A bare `--name` is passed as
`true`. The extension receives a `command:<COMMAND>` event with those options
as its payload, and the command prints the action results as JSON.

If a manifest declares `triage`, then `downcroc triage --limit 10` and
`downcroc extension run reply-bot triage --limit 10` follow the same path. The
short form exists so an extension can feel like part of the CLI.

## Common flags

`--json` prints machine-readable output instead of a table on every command
that has a tabular form.

`--timeout TIMEOUT` sets how long the CLI waits for the daemon. It does not
change the extension's own `extensions.call_timeout_s`.

The other common flags, `--no-input`, `--wide`, `--full`, `--glyphs`, `--color`,
`--quiet`, and `--no-pager`, behave as they do elsewhere in the CLI.

## When things go wrong

The daemon must be running. An extension command cannot manage a stopped
daemon.

The id must be known. Add and reload a manifest before enabling, testing, or
running it.

Capabilities are checked on every call. An ungranted capability is denied and
written to the log. `http.request` is limited to hosts granted in config, and
an unlisted host is refused before any network call happens.

A broken extension cannot take down the daemon. Crashes and timeouts are
logged and restarted up to `extensions.max_restarts`. Read
[Extension log events](events.md) for the sequence to look for.

No raw credential is returned by a capability, printed by this command, or
written to an event. The extension only ever holds a reference such as
`account:<id>`.

## Examples

`downcroc extension list` shows every discovered extension and whether it is
running.

`downcroc extension add ./reply-bot.toml` installs a manifest from your current
directory.

`downcroc extension reload` makes the daemon notice a manifest you just added.

`downcroc extension enable reply-bot` starts it and lets it receive events.

`downcroc extension test reply-bot --input '{"event":"reply.attributed","message":"msg_1"}'` runs one event through the whole path.

`downcroc extension logs reply-bot --follow` watches only that extension's
events while you try it.

`downcroc extension disable reply-bot` stops it without deleting the manifest.

## See also

- [Writing an extension](authoring.md) — build one from an empty directory
- [Wire protocol](protocol.md) — exact frames and shapes
- [Capabilities](capabilities.md) — every call with examples
- [Elevated extensions](elevated.md) — tiers and approval
- [Artifacts](artifacts.md) — build, verify, and replace a `.pyz`
- [Troubleshooting](troubleshooting.md) — common failures
- [Extension log events](events.md) — what the host records
- [../../part-iii/38-config.md](../../part-iii/38-config.md) — extension host settings
- [../17-config/config.md](../17-config/config.md) — viewing and setting config
- [../19-logs/logs.md](../19-logs/logs.md) — reading the daemon log

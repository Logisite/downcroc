---
title: serve
commands: [serve]
flags: []
concepts: [vault]
screens: []
---

# serve

`serve` runs the downcroc daemon in the foreground. It starts the daemon in the current process and keeps it attached to your terminal, instead of detaching it into the background the way `downcroc service start` does.

## Usage

```text
downcroc serve
```

`serve` takes no command-specific flags.

Common flags: `--json`, `--no-input`, `--yes`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Behavior

`serve` resolves the runtime paths and runs the daemon in the foreground in the current session. The daemon stays running until you stop it (for example by interrupting the process).

On a clean shutdown the daemon stops its inbound workers and locks the [[vault]], so credentials are not left usable after a normal exit. Starting or running the daemon does not unlock the vault; if credentials are needed, unlock it with `downcroc vault unlock`.

## When to use `serve` vs `service start`

- **`downcroc serve`** runs the daemon in the foreground, tied to the current terminal/session. This is useful when you want the daemon’s lifetime attached to that session, or when you want to run and observe it directly.
- **`downcroc service start`** starts the daemon detached in the background and records it so it can be managed as a service (`stop`, `restart`, `status`). Use `downcroc service install` to register a service definition with the system’s service manager if you want it managed there.

Both run the same daemon; the difference is whether it stays attached to your terminal or runs detached.

## Examples

- `downcroc serve` — run the daemon in the foreground in the current terminal.

## See also

- [service.md](service.md) — start, stop, restart, install, and pause the daemon as a service
- [../04-vault/vault.md](../04-vault/vault.md) — unlock the vault so credentials can be used
- [../02-status/status.md](../02-status/status.md) — overall daemon, vault, accounts, and queue status
- [../19-logs/logs.md](../19-logs/logs.md) — inspect what the daemon did
- [../part-i/01-starting/turn-it-on.md](../part-i/01-starting/turn-it-on.md) — turning the daemon on and off

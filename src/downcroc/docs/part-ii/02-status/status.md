---
title: status
commands: [status]
flags: []
concepts: [vault, failed]
screens: []
---

# status

`status` gives you a one-screen health summary of downcroc. It reports the state of the daemon and, when the daemon is running and reachable, the [[vault]], sending, accounts, queue, and recent failures. It is a read of the whole system: it never changes anything.

Use it as the first place to look when you want to know “is everything okay, and if not, where?” It tells you what needs attention and points you at the more specific commands (for example `downcroc failed`, `downcroc doctor`, or `downcroc logs`) when you need detail.

## Usage

```text
downcroc status
```

`status` takes no command-specific flags.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Output

### Daemon and paths

`status` always reports the daemon state and the local paths, even if the daemon is not running.

**Daemon state**

- **Running:** shows the daemon as running with its pid and URL.
- **Stopped:** shows that the daemon is stopped and suggests `downcroc service start`.
- **Stale** (a recorded process is gone): reports a stale daemon and suggests starting the service.
- **Not answering** (the process exists but is not responding): reports that it is not answering and suggests checking recent logs.

**Paths and log**

- Reports the config and data paths.
- Reports the log file path and its last write age, so you can see where the daemon log lives on this machine and whether it has been written to recently. (You can read that log with `downcroc logs`.)

### When the daemon is running and reachable

If the daemon is reachable, `status` also reports the live state of the system:

**Connectivity** (when applicable)
- When connectivity is disabled/offline, shows that network work is paused and since when.

**[[Vault]]**
- The vault state (for example locked or unlocked), so you can tell at a glance whether credentials can be used.

**Sending**
- `running` when sending is proceeding normally.
- Paused when sending is held at the service level, including since/until (when applicable), the reason, and the number of held jobs and batches. (A service-level pause holds dispatch without changing policy values; see `downcroc service pause/resume`.)

**Accounts**
- The total number of accounts and any that need attention. This includes accounts that need re-authentication ([[needs-reauth]]) or are pending, along with a hint to reconnect and the reported auth error when available. Accounts in a healthy, connected state do not need attention.

**Queue**
- Totals of sent jobs and [[failed]] jobs, giving you a quick sense of throughput and whether anything has failed.

**Failed**
- The most recent failed job (recipient and code), when there is one, so you can see the latest failure without digging further. For the full picture and to act on failures, use `downcroc failed`.

### JSON output

With `--json`, `status` prints a machine-readable object containing the daemon report and, when the daemon is running, the vault, sending, accounts, summary, failed entries, and log info.

## Exit status

`status` exits `0` when the daemon is running. It exits non-zero when the daemon is stopped, stale, or unreachable. This makes it usable in scripts or checks that need to know whether the daemon is healthy.

## `status` vs `service status`

`downcroc status` and `downcroc service status` answer related but different questions:

- **`downcroc status`** is a whole-system health summary: daemon state and paths plus, when running, vault, sending, accounts, queue, and recent failures.
- **`downcroc service status`** reports the service/daemon process state (and service-level sending hold) from the service-management perspective.

Use `status` for the big picture; use `service status` when you care specifically about the service process and its sending hold.

## Examples

- `downcroc status` — print the health summary for the daemon, paths, vault, sending, accounts, and queue.
- `downcroc status --json` — print the same information as machine-readable JSON.

## See also

- [../01-service/service.md](../01-service/service.md) — control the daemon service and service-level sending pause
- [../01-service/serve.md](../01-service/serve.md) — run the daemon in the foreground
- [../04-vault/vault.md](../04-vault/vault.md) — create, unlock, and lock the vault
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose the installation and transports
- [../10-failed/failed.md](../10-failed/failed.md) — inspect and retry failed jobs
- [../19-logs/logs.md](../19-logs/logs.md) — read and understand the daemon log (exact path shown by `status`)
- [../19-logs/events/index.md](../19-logs/events/index.md) — meanings of log events and fields
- [../part-i/03-keeping-it-running/the-daily-round.md](../part-i/03-keeping-it-running/the-daily-round.md) — the daily check-in
- [../part-i/03-keeping-it-running/problems-list.md](../part-i/03-keeping-it-running/problems-list.md) — where problems surface and how to read them in order

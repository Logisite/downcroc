---
title: service
commands: [service]
flags: [--print, --for, --reason]
concepts: []
screens: []
---

# service

`service` controls the downcroc daemon as a managed service: you can start, stop, restart, or inspect it, install or remove its service definition, and pause or resume sending at the service level. These actions manage the daemon process and service registration; they do not change your batches, jobs, accounts, or their policies.

The [[daemon]] is the part that owns state and does the work (sending, watching, syncing). When it runs, it listens on a local loopback address and other downcroc commands talk to it over that local API. `downcroc service start` runs it detached in the background; to keep it attached to your terminal instead, use `downcroc serve`.

## Usage

```text
downcroc service [start|stop|restart|status|install|uninstall|pause|resume]
                 [--print] [--for DURATION] [--reason REASON]
```

If you omit the action, downcroc asks you to choose one (in the interactive menu you can pick the action directly).

## Actions

### start

Starts the [[daemon]] as a detached background process and records it in `service.json` (including its pid, host, port, start time, and version) so other commands can find it.

**On success**

- Reports that the daemon is running with its pid and URL.
- Suggests unlocking the [[vault]] next with `downcroc vault unlock`. Starting the daemon does **not** unlock the vault, and a clean start/stop cycle leaves the vault locked, so credentials are not usable until you unlock it.

**If it is already running**

- If the daemon is already running and healthy, `start` reports that it is already running and makes no change.

**If it cannot start cleanly**

- If a pid exists but the daemon is not answering, `start` fails with a start error and suggests stopping the service and starting it again (this clears a wedged state where a recorded process is not responding).
- On other start failures it suggests inspecting recent logs with `downcroc logs --since 5m` to see what went wrong.

`start` runs the daemon detached. For a foreground run tied to your terminal, use [`downcroc serve`](serve.md).

### stop

Stops the daemon.

- Reports `stopped` when it stopped a running daemon, or `not running` when there was nothing to stop.
- On a clean shutdown the daemon stops its inbound workers and locks the vault. A stopped daemon is not processing work, and it ends up locked.

### restart

Stops the daemon and then starts it again. It follows the same reporting and failure behavior as `stop` followed by `start`: if the stop or the subsequent start runs into trouble, you get the corresponding messages and hints.

### status

Reports the service and daemon state. This action only reads state; it never changes it.

**When the daemon is running**

- Reports the daemon as running with its pid and URL, plus version, start time, and uptime when those are available.
- Also reports sending state: either `running`, or paused — and when paused it includes since/until (when applicable), the reason, and the number of held jobs and batches.

**When the daemon is not running normally**

- **Stopped:** reports `stopped` and suggests starting the service. Exits non-zero.
- **Stale** (the recorded pid is gone): reports a stale daemon and suggests starting the service. Exits non-zero.
- **Unreachable** (a pid is present but the daemon is not answering): reports that it is not answering and suggests checking recent logs. Exits non-zero.

`service status` exits `0` only when the daemon is running and healthy. It is focused on the service/daemon process state (and the service-level sending hold). For a broader, whole-system view — daemon, paths, vault, sending, accounts, and queue together — use [`downcroc status`](../02-status/status.md).

### install

Installs the service definition so the daemon can be managed by the system’s service manager.

- **`--print`**: prints the service definition without installing it. The definition is written as text, or as JSON when `--json` is set. This has no side effects and is useful for inspecting what would be installed or for debugging.
- **Without `--print`**: installs the definition and reports the service kind and path, then suggests starting the service.
- **On failure:** reports a service install error and suggests inspecting the definition with `downcroc service install --print`.

Installing registers the service; it does not by itself start it (use `start` or let the service manager run it).

### uninstall

Removes the installed service definition.

- Reports whether the service was uninstalled (with kind and path) or was not installed.
- Uninstalling removes the service registration only; **your data stays in place**. The data and config paths are shown by `downcroc status`.

### pause

Pauses sending at the service level. While paused, the daemon holds sends instead of dispatching them — work remains queued/held rather than being sent out.

**Requirements and limits**

- Requires the daemon to be running. If the daemon is not running, `pause` fails with `daemon_not_running` and notes that a stopped daemon already sends nothing. (A hold that must outlive a stop cannot be set on a stopped daemon, because there is no running daemon to hold the state across that boundary in that form.)

**Duration and reason**

- `--for DURATION` sets how long the pause lasts, for example `30s`, `15m`, `2h`, or `7d`. With `--for`, the pause is timed: it expires on its own and sending resumes automatically when the duration elapses.
- Without `--for`, sending stays paused until you explicitly resume it.
- `--reason REASON` records why sending is paused. The reason, along with since/until and held job/batch counts, is shown by `service status` and reflected in the overall status.

**What a service-level pause does and does not do**

- Pausing here is a service-level hold on dispatch. It does **not** cancel, reassign, delete, or rewrite jobs or batches, and it does not change send policy values.
- It is separate from pausing a batch, pausing a job, pausing an account, or changing global/per-account sending policy and overrides. Those are different controls that affect different scopes.

### resume

Resumes sending at the service level and clears the service hold.

- `--reason REASON` can record why sending was resumed.
- Reports that sending is running. If a timed pause had already expired, sending may already have resumed automatically; `resume` makes sure the service-level hold is cleared.

## Options

`--print`
: Print the service definition without installing it. Used with `install`.

`--for DURATION`
: How long to pause sending, for example `30s`, `15m`, `2h`, or `7d`. Used with `pause`. Without it, the pause lasts until you resume.

`--reason REASON`
: Why sending is paused or resumed. Used with `pause` and `resume`.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Output and events

- With `--json`, commands emit machine-readable JSON (for example the service record on start/install/uninstall, state on status/stop, or the pause/resume result with sending state and whether it changed).
- Pausing records a `service.paused` event. Resuming records `service.resumed`. A pause that expires on its own records `service.resumed` with reason `expired`.

## Examples

- `downcroc service start` — start the daemon in the background and report its pid and URL.
- `downcroc service status` — show whether the daemon is running and, when it is, whether sending is running or paused (with held counts).
- `downcroc service restart` — stop and start the daemon.
- `downcroc service stop` — stop the daemon.
- `downcroc service pause --for 2h --reason "maintenance"` — pause sending at the service level for two hours and record the reason.
- `downcroc service pause --reason "investigating"` — pause sending until resumed explicitly.
- `downcroc service resume` — resume sending at the service level.
- `downcroc service install --print` — print the service definition without installing it.
- `downcroc service install` — install the service definition.
- `downcroc service uninstall` — remove the service definition while keeping data.

## See also

- [serve.md](serve.md) — run the daemon in the foreground
- [../02-status/status.md](../02-status/status.md) — overall daemon, vault, accounts, and queue status
- [../04-vault/vault.md](../04-vault/vault.md) — unlock the vault after starting the daemon
- [../11-sending/sending.md](../11-sending/sending.md) — global sending policy and overrides
- [../19-logs/logs.md](../19-logs/logs.md) — read and understand the daemon log
- [../19-logs/events/service-holds.md](../19-logs/events/service-holds.md) — log events for service pause/resume and holds
- [../part-i/01-starting/turn-it-on.md](../part-i/01-starting/turn-it-on.md) — turning the daemon on and off
- [../part-i/03-keeping-it-running/stuck.md](../part-i/03-keeping-it-running/stuck.md) — when work is paused or not moving

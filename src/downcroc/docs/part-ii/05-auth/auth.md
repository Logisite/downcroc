---
title: auth
commands: [auth, auth.status]
flags: []
concepts: []
screens: []
---

# auth

`auth` lets you inspect whether your local CLI session can authenticate to the running downcroc daemon.

The daemon’s local API is protected by a per-run bearer token stored alongside the service state. Most `downcroc` commands talk to the daemon using that token; if the token is missing, stale, or rejected, commands that need the daemon cannot act on your behalf. `auth` gives you a direct way to check that this handshake is healthy.

## Usage

```text
downcroc auth status
```

## Actions

### status

Checks the daemon token and reports whether the daemon accepts it.

`downcroc auth status` looks at the current service state and the local API token, then (when possible) makes an authenticated request to the daemon to confirm the token is accepted.

**What it checks and reports**

- **Daemon state:** whether downcroc is `running`, `stopped`, or `unreachable` (a recorded service exists but the daemon does not answer).
- **Token presence:** whether a local API token is present (`token_present`).
- **Acceptance:** whether the daemon accepted the token (`accepted`). When the daemon is running and a token is present, `auth status` calls the daemon’s status endpoint with the bearer token; `accepted` is true only if that request succeeds (HTTP 200).
- **Daemon details (when running):** the daemon pid and URL.

**Output**

- Default: prints a short human-readable result and, when something is wrong, a suggested next step.
  - Stopped: reports that downcroc is not running and suggests `downcroc service start`.
  - Unreachable: reports that the daemon does not answer and suggests `downcroc logs --since 5m`.
  - No token: reports that there is no API token and suggests `downcroc service restart`.
  - Rejected: reports that the daemon rejected the API token and suggests `downcroc service restart`.
  - Accepted: reports that the token is accepted and shows the daemon pid/URL.
- With `--json`: prints a machine-readable object containing `state`, `token_present`, `accepted`, and (when running) `pid` and `url`.

**Exit status**

- Exits `0` when the daemon is running and the token is accepted.
- Exits non-zero when downcroc is stopped, unreachable, missing a token, or the token is rejected.

`auth status` is read-only; it does not change the daemon, the token, or any service state.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc auth status` — check whether the daemon accepts the local API token.
- `downcroc auth status --json` — print the same check as machine-readable JSON (useful in scripts).

## See also

- [../01-service/service.md](../01-service/service.md) — start, stop, or restart the daemon/service
- [../02-status/status.md](../02-status/status.md) — overall daemon, vault, accounts, and queue status
- [../19-logs/logs.md](../19-logs/logs.md) — read the daemon log (useful when the daemon is unreachable)
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose the installation and transports

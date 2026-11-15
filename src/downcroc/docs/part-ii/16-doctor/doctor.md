---
title: doctor
commands: [doctor, doctor.transports, doctor.capacity, doctor.inbound]
flags: []
concepts: []
screens: []
---

# doctor

`doctor` diagnoses the installation and the health of transports and inbound processing. Use it when something is not working and you want downcroc to check its own setup, or when you want a focused report on send transports, fleet capacity, or inbound mailbox state.

`downcroc doctor` with no subcommand runs a set of local installation checks. The subcommands query the running daemon for deeper, live diagnostics about transports, capacity, and inbound.

## Usage

```text
downcroc doctor [subcommand]
```

Subcommands: `transports`, `capacity`, `inbound`.

## Running doctor with no subcommand

```text
downcroc doctor
```

Runs installation and environment checks and reports each one with a pass/fail result. It does not modify anything.

**Checks performed** (as reported): configuration parses (and the config path), paths are writable (config/data/state directories), the database exists, the daemon is alive/running, the service definition is installed, the log file/path and its last write age, the credential store status (available/unavailable with reason), plus account/provider readiness signals (for example accounts needing attention such as re-authentication, and provider readiness/missing configuration) with suggested fixes where applicable.

**Output**

- Default: prints each check with its status and detail; for failing checks it prints a suggested fix when one is known. Ends with a summary (“every check passed” or how many checks need attention).
- With `--json`: prints `{"ok": <bool>, "checks": [...]}` where `ok` is true only when no checks failed.

**Exit status**

- Exits `0` when every check passes.
- Exits `1` when any check needs attention.

## Subcommands

The subcommands contact the running daemon and report live diagnostics. They require the daemon to be reachable.

### transports

```text
downcroc doctor transports
```

Checks send bindings (transports) and OAuth clients.

**What it reports**

- **Bindings:** for each account transport/binding, the account and address, transport kind, health/problem state (including a problem reason when present, such as a missing OAuth client, needs re-auth, pending/unverified/disabled account or binding), priority, concurrency/limit, and associated OAuth client id (when applicable).
- **OAuth clients:** imported clients (id, provider, project, client id) known to the system.
- **Checks:** per-binding checks (for example vault/credential availability, OAuth client validity, token/API/scope/clock checks as applicable to the transport). Failing checks are shown with account, binding, check name, code, and detail.

**Output**

- Default: prints bindings, clients, and any failing checks, then a result line (“transports healthy” or “transports need attention”).
- With `--json`: prints the full transports diagnostic payload (including `ok`, bindings, clients, checks/problems).

**Exit status:** `0` when healthy (`ok`), `1` when transports need attention.

### capacity

```text
downcroc doctor capacity
```

Reports fleet capacity: lanes, seats, and SMTP-only mailboxes, plus queue/wait/hold signals.

**What it reports**

- **Fleet/lanes:** total lanes, API lanes, SMTP seats (active/configured), whether sending is effectively serial in this configuration, parallel-sends/API concurrency settings, and bindings per kind.
- **Activity and queue:** active SMTP slots, queued and waiting accounts, counts of password/OAuth accounts and OAuth-API-only accounts, password accounts waiting, reserved quota units, and held pinned jobs.
- **Accounts/seats:** SMTP-only (and password-only) mailboxes, accounts waiting for a slot, paused accounts (with since/reason), and idle seats.
- **Warnings and guidance:** a warning and risk level when SMTP seat configuration is risky (for example seats above safe levels; extra seats do not create parallel SMTP capacity and may increase provider risk), and a recommendation when password-only mailboxes limit you to SMTP (suggesting an OAuth/Gmail API lane for throughput).

**Output**

- Default: prints a capacity summary, queue/wait/hold counts, and lists of SMTP-only/waiting/paused/idle items, plus any warning/recommendation.
- With `--json`: prints the full capacity diagnostic payload (including `ok`, lanes/seats, counts, lists, warning/risk/recommendation).

**Exit status:** `0` when healthy (`ok`), `1` when capacity needs attention (for example an unsafe seat configuration is flagged).

### inbound

```text
downcroc doctor inbound
```

Reports inbound ownership, cursors, and failures for watched/connected accounts.

**What it reports**

- **Summary:** inbound sources in use (e.g. IMAP vs Gmail API counts), number of stale/problem accounts, and the idle fleet cap.
- **Per account:** account id/address, inbound owner and mode, cursor state (IMAP uidvalidity/last uid, or Gmail history id as applicable), last connected/event/sync/sweep times, consecutive failures, last error, and whether the idle cap applies.

**Output**

- Default: prints the summary and per-account rows, then a result line (“inbound healthy” or “inbound needs attention”).
- With `--json`: prints the full inbound diagnostic payload (including `ok`, accounts, sources, stale, idle_fleet_cap).

**Exit status:** `0` when healthy (`ok`, no stale/problem accounts reported), `1` when inbound needs attention.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc doctor` — run installation checks and show what needs attention.
- `downcroc doctor transports` — check send bindings, OAuth clients, and transport checks.
- `downcroc doctor capacity` — review lanes, SMTP seats, and queue/wait/hold capacity.
- `downcroc doctor inbound` — inspect inbound owners, cursors, and recent failures.
- `downcroc doctor --json` — print installation check results as JSON.

## See also

- [../02-status/status.md](../02-status/status.md) — overall system health summary
- [../07-account/account.md](../07-account/account.md) — accounts, transports, and policy
- [../06-provider/provider.md](../06-provider/provider.md) — provider declarations and OAuth clients
- [../19-logs/logs.md](../19-logs/logs.md) — read the daemon log for detail
- [../19-logs/events/accounts-auth.md](../19-logs/events/accounts-auth.md) — auth/login and account log events
- [../19-logs/events/inbound-watcher.md](../19-logs/events/inbound-watcher.md) — inbound/watcher log events
- [../part-i/03-keeping-it-running/problems-list.md](../part-i/03-keeping-it-running/problems-list.md) — where to look when something is wrong

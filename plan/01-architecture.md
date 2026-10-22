# 01 - Architecture

## Process model

One daemon. It is the only component that owns state, credentials, network connections, and
background work. Clients are renderers with input handling; they call the API and subscribe
to events.

```
             +----------------------+
             |      downcroc TUI    |        (Textual, HTTP + SSE)
             +----------+-----------+
                        |
             +----------+-----------+
             |   HTTP API (loopback)|        (FastAPI, no auth, see 04)
             |   + SSE event stream |
             +----------+-----------+
                        |
             +----------+-----------+
             |      core services   |
             |  accounts  vault     |
             |  batches   jobs      |
             |  dispatch  watchers  |
             |  threads   stats     |
             +----------+-----------+
                        |
        +---------------+---------------+
        |               |               |
   SQLite           content store     vault.enc
   (state, mail)    (batches,         (credentials)
                     templates,
                     attachments)
```

The API layer is a thin adapter over core services. It contains no business rules, no retry
logic, and no knowledge of providers. If the API were deleted, the core would still work
under test, driven directly.

Clients are forbidden from:

- opening SQLite
- reading the vault
- touching the content store for writes
- calling IMAP or SMTP
- keeping state that the daemon does not also know

A client may cache a rendered view. It may not become the authority for anything.

## Event loop and threads

One `asyncio` event loop carries the API, the SSE fan-out, the dispatcher, SMTP sends, OAuth
refresh, and SQLite access (through a small executor-backed wrapper so writes never block
the loop).

Two places use threads, deliberately and with narrow boundaries:

| Work | Model | Why |
|---|---|---|
| SMTP send | `aiosmtplib` on the loop | Short lived, cancellable, needs a fresh token per send |
| IMAP fetch and IDLE | `imap-tools` in one dedicated thread per watched account | The library is synchronous; IDLE is a long-lived blocking call |

Each IMAP thread owns exactly one connection and one mailbox. It never touches SQLite and
never touches the API. It pushes work onto an `asyncio.Queue` through
`loop.call_soon_threadsafe` and returns results the same way. All database writes happen on
the loop thread as a consequence.

IDLE threads carry a socket timeout a little shorter than the server's idle limit, so a
stuck thread always returns on its own instead of hanging shutdown. Shutdown signals the
thread, waits briefly, and then abandons it as a daemon thread rather than blocking the
process.

## On-disk layout

```
~/.config/downcroc/
  config.toml              # the only source of truth for configuration
  templates/               # template files, edited through the TUI
  providers.toml           # optional provider overrides, see 05

~/.local/share/downcroc/
  downcroc.db              # SQLite, WAL mode
  content/                 # content store: batches, attachments
  failed.jsonl             # permanent failures, retryable from the TUI
  logs/downcroc.jsonl      # one JSON object per line, rotating, 10 MB x 5
  attachments/             # received attachment files

~/.local/state/downcroc/
  service.json             # pid, port, started_at, version
```

Permissions: the vault, `config.toml` and provider overrides are `0600`. The data directory
is `0700`.

## Configuration versus state

A single rule resolves where a thing lives:

- **Config** is how the system is allowed to behave. It lives in `config.toml`, is
  human-editable, and is the only source of truth.
- **State** is what is currently true. It lives in SQLite and is never hand-edited.

So a daily allowance, an active window, or a jitter range is config. A watcher toggle, a
quota counter, a job, or a UID cursor is state. The TUI edits config by calling the API, and
the daemon rewrites `config.toml` atomically and reloads. Two stores never disagree.

## Daemon lifecycle

The daemon is expected to run continuously on this machine. Scheduling, retries, and watchers
only have meaning if the process is up.

| Command | Effect |
|---|---|
| `downcroc` | discovers or starts the daemon, then attaches the TUI |
| `downcroc service start` | start detached |
| `downcroc service status` | pid, address, uptime, vault state, queue counts |
| `downcroc service stop` | stop. This locks the vault |
| `downcroc serve` | run in the foreground, for systemd or containers |
| `downcroc web` | attach the browser client (later) |
| `downcroc restore <bundle>` | restore while the daemon is stopped |
| `downcroc stats rebuild [--since DATE]` | recompute stored aggregates from the source rows |
| `downcroc logs [filters]` | query the log file, pretty on a terminal, raw JSON with `--json` |

Lifecycle rules:

1. The daemon starts **locked**. It needs no password to start, so it can start from systemd
   at boot and wait.
2. Unlock is an explicit, separate event: the TUI asks for the master password and posts it
   once, or the CLI does the same. The daemon derives the key, keeps it in memory, and
   discards the password.
3. Stopping the daemon locks the vault by definition. There is no idle timer and no
   auto-lock while running, because the process dying is the lock.
4. A daemon that is running but locked does everything that does not need a credential:
   serve the API, list accounts, render jobs, serve history, report stats.
5. A daemon that is running and unlocked sends, fetches, and refreshes tokens.
6. On restart, jobs that were `sending` are reconciled before anything else runs, and their
   leases are expired. See `03-data-model.md`.
7. `SIGTERM` and `SIGINT` stop the daemon cleanly: it stops accepting, logs `daemon.stopping`
   with the signal and uptime, removes `service.json`, releases the lock, and exits 0. The
   signal is not re-raised, so a supervisor reads a clean stop rather than a signal death.
   `kill -9` skips all of it; the kernel drops the lock and the next start replaces the stale
   `service.json`.

## Discovery

`service.json` is written atomically on start and removed on clean stop. It holds pid, port,
started_at, and version. A client:

1. reads `service.json`
2. probes `GET /api/health`
3. if healthy and the version matches, attaches
4. if stale, removes the file and starts a daemon

A live lock file prevents two daemons. The second one exits with a clear message rather than
fighting for the database.

## Loopback binding

The API binds `127.0.0.1` only. Port selection: a fixed configured port when set, otherwise
an ephemeral port recorded in `service.json`.

There is no authentication on the API. This is a deliberate decision recorded in `04` and
`11`. It means any process running as any local user can read your mail and queue sends
within your configured allowance while the daemon is unlocked and running. The vault exists
to protect credentials at rest, not to gate the live API.

## Package layout

```
src/downcroc/
  ports/         protocols between layers, no implementations
  domain/        pure types and rules, no I/O
  store/         sqlite, migrations, repositories, content store, search
  vault/         kdf, envelope encryption, atomic write
  providers/     declarations, oauth, token refresh
  mail/          smtp sender (aiosmtplib), imap transport (imap-tools), mime
  html/          sanitize for display, inline css for send
  core/          services, dispatch, inbound, rendering, stats
  api/           routes, schemas, sse, errors
  tui/           textual app, screens, widgets, api client
  backup/        bundle create, verify, restore
  runtime/       config, paths, logging, clock, ids, service control
  cli/           command surface, service control
```

Dependencies point inward. `core` knows nothing about FastAPI, Textual, or imap-tools; it talks
to protocols in `ports/`. Concrete adapters are wired once in `core/bootstrap.py`. That is the
modularity the project requires, and it is what makes a provider, a transport, or a client
replaceable without touching the queue.

The full tree, three levels deep, with the seam table and the rule for which library may live
where, is in `12-module-map.md`.

## Failure philosophy

Every state the daemon can be in has a defined, persisted form, and the restart path is the
primary path, not an afterthought.

- No work exists only in memory.
- No long operation holds a row without a lease.
- No retry is unbounded.
- No client is required for progress.
- No failure is silent; every terminal failure is visible in the TUI with a reason.

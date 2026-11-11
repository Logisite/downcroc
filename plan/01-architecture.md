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
             |   HTTP API (loopback)|        (FastAPI, bearer auth, see 04)
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

So the `[sending]` defaults for a daily allowance, an active window, or a jitter range are
config. A newly added account copies those defaults into its own policy, which is state because
it is different for each account and edited per account. A watcher toggle, a quota counter, a
job, or a UID cursor is state too. Global behaviour is edited through `config.toml` and reloaded;
per-account policy is edited through the account API. Each value has exactly one home, so two
stores never disagree.

## Daemon lifecycle

The daemon is expected to run continuously on this machine. Scheduling, retries, and watchers
only have meaning if the process is up.

| Command | Effect |
|---|---|
| `downcroc` | show daemon status |
| `downcroc service start` | start detached |
| `downcroc service status` | pid, address, uptime, vault state, queue counts |
| `downcroc service stop` | stop. This locks the vault |
| `downcroc service install` | install a systemd user unit or a logon task |
| `downcroc service uninstall` | remove the native service and keep config, data, and state |
| `downcroc serve` | run in the foreground, for systemd or containers |
| `downcroc vault status` | show whether the vault is locked |
| `downcroc vault unlock` | unlock and start inbound workers |
| `downcroc vault lock` | lock and stop inbound workers |
| `downcroc account ...` | list, add, remove, connect, verify, sync, and watch accounts |
| `downcroc batch ...` | preview, submit, approve, cancel, and add follow-ups |
| `downcroc job ...` | list, show, create, and send jobs |
| `downcroc failed ...` | list and retry permanent failures |
| `downcroc mail ...` | browse stored messages, threads, and attachments |
| `downcroc config ...` | show, describe, and change settings |
| `downcroc stats ...` | read totals, rebuild aggregates, and prune expired rows |
| `downcroc backup [path]` | write a bundle, optionally into a directory with a generated name |
| `downcroc restore <bundle>` | restore while the daemon is stopped |
| `downcroc logs [filters]` | query the log file, pretty on a terminal, raw JSON with `--json` |

Human output is plain when piped and colourised on a terminal. `NO_COLOR=1` disables colour;
`--json` prints the raw document.

Lifecycle rules:

1. The daemon starts **locked**. It needs no password to start, so it can start from systemd
   at boot and wait.
2. Unlock is an explicit, separate event: the CLI obtains the master password, either from a
   prompt, from `--password-file`, or from the system credential store when the user opted in,
   and posts it once. The daemon derives the key, keeps it in memory, and discards the
   password. The daemon itself never reads the credential store (`13`, Q-L).
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
8. `downcroc service stop` uses the per-run bearer token to post `/api/service/stop`. The
   endpoint sets the server's shutdown flag, so the same application lifespan path runs:
   inbound stops, vault locks, the event bus closes, `service.json` is removed, and the lock
   is released. It does not signal the process directly.
9. A hard kill skips all of that; the operating system drops the lock and the next start
   replaces the stale `service.json` and rotates the bearer token.
10. `downcroc service install` writes a native user service that runs `serve` in the
    foreground under the platform supervisor: a systemd user unit or a Windows logon task.
    The definition uses the absolute launcher path and the current
    `HOME` and XDG overrides, so the supervised daemon reads the same config, data, and
    state as the CLI. Install stops a detached daemon first, then reloads and starts the
    unit. Reinstalling overwrites the one definition, so it never creates a duplicate.
    `--print` renders the definition and command plan without touching the system.
    Uninstall stops the service and removes only its definition, leaving config, data,
    and state intact. Nothing in install or uninstall needs root or administrator rights.

## Discovery

`service.json` is written atomically on start and removed on clean stop. It holds pid, port,
started_at, version, and api_version. A client:

1. reads `service.json`
2. probes `GET /api/health`
3. if healthy and the version matches, attaches
4. if stale, removes the file and starts a daemon

The daemon also writes `daemon.token` in the state directory at startup, mode `0600` on Unix
and an owner-only ACL on Windows, and removes it on clean stop. Every client reads it and sends
it as a bearer token; `service stop` uses it for the shutdown request. A live lock file prevents
two daemons. The second one exits with a clear message
rather than fighting for the database.

## Platform boundary

Paths, file permissions, locking, process liveness, and detached startup are isolated behind
`runtime/paths.py`, `runtime/fs.py`, and `runtime/service/process.py`. The lifecycle code does
not call `fcntl`, `msvcrt`, `os.fchmod`, or `O_DIRECTORY` directly.

| Concern | POSIX | Windows |
|---|---|---|
| Config | `XDG_CONFIG_HOME/downcroc` or `~/.config/downcroc` | `%APPDATA%\\downcroc` |
| Data | `XDG_DATA_HOME/downcroc` or `~/.local/share/downcroc` | `%LOCALAPPDATA%\\downcroc` |
| State | `XDG_STATE_HOME/downcroc` or `~/.local/state/downcroc` | `%LOCALAPPDATA%\\downcroc\\state` |
| Private files | `0700` directories and `0600` files | inherited user ACLs |
| Instance lock | `fcntl.flock` on the lock file | `msvcrt.locking` on the lock file |
| Liveness | `os.kill(pid, 0)` | `OpenProcess` and `GetExitCodeProcess` |
| Detached start | `start_new_session=True` | `DETACHED_PROCESS`, `CREATE_NEW_PROCESS_GROUP`, and `CREATE_NO_WINDOW` |

A `0600` mode is applied on Unix. Windows relies on the user profile ACL because Python's
`chmod` only changes the read-only bit. Directory fsync is skipped on Windows, which does not
provide the POSIX directory handle guarantee.

The full test suite runs on Linux and Windows in GitHub Actions. macOS is out of scope for
release 1: it is not tested, packaged, installed, or supported. The darwin path and service
fallbacks remain in the code but carry no support commitment, and CI does not exercise them.
Local checks stay limited to focused tests and Ruff; packaging, binaries, installers, and
release builds are CI-only.

## Loopback binding

The API binds `127.0.0.1` only. Port selection: a fixed configured port when set, otherwise
an ephemeral port recorded in `service.json`.

The API is authenticated with the per-run token from `daemon.token`. Release 1 applies the
same bearer token to every route except `GET /api/health` and the OAuth callback, which is
protected by its state nonce. The token is created at startup, mode `0600` on Unix and an
owner-only ACL on Windows, never logged, removed on clean stop, and rotated on the next
start. Requests must also carry a trusted loopback Host and, when present, a loopback Origin.
The public `/docs`, `/redoc`, and `/openapi.json` routes are disabled; `downcroc openapi`
exports the schema from inside the package.

There is no browser login, cookie, pairing flow, or GUI session. A client is any process that
can read the token file as the same user, and `downcroc auth status` reports whether that
token exists and is accepted without printing it. This closes the accidental local API
exposure recorded in `04` and `11`; it does not defend against a process that can read the
token file as the same user.

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
to protocols in `ports/`. Concrete adapters are wired once in `core/bootstrap/`. That is the
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

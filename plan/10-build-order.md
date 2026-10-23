# 10 - Build order

## Stack

| Component | Choice | Note |
|---|---|---|
| Language | Python 3.14 | the only interpreter on the machine |
| Packaging | `uv` | `uv init`, `uv add`, `uv run`. `uv.lock` committed |
| HTTP | FastAPI + uvicorn | one process, one loop |
| Validation | pydantic | schemas generate the OpenAPI document |
| Database | SQLite with SQLAlchemy 2.0 and Alembic | declarative models, generated migrations, one writer |
| SMTP | `aiosmtplib` | native `auth_xoauth2`, token generator hook |
| IMAP | `imap-tools` | synchronous, native XOAUTH2, so it runs in threads |
| Crypto | `argon2-cffi`, `cryptography` | Argon2id, AES-GCM |
| TUI | Textual | async, keyboard-first |
| HTML | `nh3` for sanitizing, `css-inline` for inlining | both active and maintained |
| Archive | `zstandard`, stdlib `tarfile` | streamed bundles |
| Formatting | `ruff format` | runs with its own defaults; the repo holds no `[tool.ruff]` config |

No dependency is added for a job that a hundred lines of stdlib does. Every dependency above is
load-bearing: mail protocols, crypto, UI, or archive format.

Dependencies are added with `uv add <package>` and never by editing the dependency table by hand.
Version selection is uv's job, not ours.

## Phases

Each phase is shippable in the sense that the daemon runs and does not lose data. Each has a gate
that must pass before the next one starts, and the gate is a live check against a running daemon
with the commands and the expected output written down, not a checklist item someone ticks.

### P0 - Skeleton

Repo, uv project, CLI surface, config load and validation, logging with redaction, XDG paths,
database open plus `alembic upgrade head` at startup, `service.json`, daemon start/stop, health
and status endpoints, empty TUI that attaches.

**Gate:** `downcroc service start` then `stop` then `start` works. Two daemons cannot run. The
TUI attaches to a running daemon and shows the empty states without a traceback. A version
mismatch refuses cleanly.

### P1 - Vault and accounts

Vault format, Argon2id tuning, unlock and lock, atomic writes, account CRUD, generic IMAP with an
app password, verify action, credential presence in the UI, redaction at the logging boundary.

**Gate:** wrong password fails cleanly and is throttled; a damaged vault (truncated, or one byte
changed) is detected and does not crash the daemon; credentials never appear in any HTTP response,
log line, or event, confirmed by sending one message and reading the live log. Restart leaves the
daemon locked and the accounts listed.

### P2 - Inbound

IMAP sync, UID cursor, UIDVALIDITY handling, IDLE loop with timeout and reconnect, message
storage, attachment extraction, mailbox screen, thread table, subject normalization.

**Gate:** 500 messages ingested in order with zero duplicates across three forced reconnects and
one UIDVALIDITY reset. A dropped network for two minutes recovers without operator action. Memory
stays flat while a 5,000-message folder is scanned.

### P3 - OAuth and send, single message

Connect attempts with loopback callback, token storage and refresh, XOAUTH2 for Gmail and
Microsoft, `needs_reauth` state, MIME building, one manual send to one address, Sent-folder
reconciliation of `sent_unconfirmed`.

**Gate:** connect an account end to end, send one message, receive it, and show it as sent. Kill
the daemon between SMTP acceptance and the database commit, restart, and confirm the job ends
`sent` rather than duplicated. Force a token expiry and confirm a single refresh, not a loop.

### P4 - Batch pipeline

JSON ready-message campaigns, CSV plus templates, rendering, validation, snapshots, routing and
account binding, dry-run approval, dispatcher, quota buckets, windows, jitter, concurrency limits,
retries, failures file.

**Gate:** 1,000 jobs across 10 accounts at a configured 200/day each, with a 2 second jitter
range, complete in the expected window and never exceed any counter. `kill -9` mid-drain, restart,
and the remaining jobs continue with no duplicate to any recipient. A restart at 23:59 does not
reset an allowance. Retry a batch of 50 permanent failures and confirm the reasons and the file.

**This is the phase where the product is actually proven.** Everything before it is
infrastructure.

### P5 - Attribution

Thread linking by headers, probable matching, DSN classification, reply counts, batch and
recipient drill-down, suppression, follow-up batches, reply window, late replies.

**Gate:** against a live mailbox seeded with 300 known replies and 40 bounces, the batch reports at
least 97 percent confirmed replies and counts zero bounces as replies. Suppression excludes exactly
the repliers and nobody else. A follow-up lands in the same thread in Gmail, Outlook, and one
generic server.

### P6 - Operations

Retention and pruning, hourly and daily aggregates with rebuild, failure retry from the TUI, config hot reload,
backup and restore, log rotation, startup reconciliation of every ambiguous state.

**Gate:** backup a populated installation, wipe it, restore into an empty directory, and get
identical counts, identical reply attribution, and a working queue. A bundle from an unknown
newer revision is refused, naming the revision. Retention prunes correctly and reports what it
removed.

### P7 - Client polish

Approval modal states, empty and error states, keybindings and help, settings form generated from
schema, template editing, failure screen, the design-law pass from `08-tui.md`, and a full
accessibility pass on colour and truncation.

**Gate:** a person who has not seen the tool can add an account, import a 20-row CSV, run the dry
run, approve the batch, and read the reply count without being told where to click. Every binding
in `?` does something.

## The acceptance workflow

Run once at the end, on a real machine, with real accounts, because this is the only test that
proves the thing is worth using.

| Step | Expected |
|---|---|
| 1 | fresh install, start, unlock, add 10 accounts across all three provider types |
| 2 | import a 1,000-message JSON campaign, see validation and routing, approve 5 samples |
| 3 | send one sample, verify it in Gmail by hand |
| 4 | approve the rest, watch the account rail burn down |
| 5 | reply to 100 of them from a separate mailbox, over a day |
| 6 | batch shows `~110 inbound (100 replies)` with a plausible gap |
| 7 | `kill -9` the daemon during sending, restart, confirm no duplicates |
| 8 | submit a follow-up, confirm suppressions and threading |
| 9 | backup, wipe, restore, confirm the same numbers |
| 10 | stop the daemon, confirm the vault is locked and credentials are unreadable |

Step 5 is the one nobody can automate, and it is the one that decides whether the reply counting
is honest.

## Acceptance tests

The acceptance suite is black-box and lives in `tests/`. It starts the real daemon with an
isolated HOME and XDG directories, drives real HTTP, real SQLite, and the real content store, and
fakes only the external network boundary: SMTP, IMAP, and OAuth. No daemon module, service,
repository, or route is mocked.

```
tests/
  conftest.py            fixtures only
  harness/
    daemon.py            start, wait, stop the real daemon
    api.py               typed loopback client
    fakes.py             SMTP, IMAP, OAuth stand-ins
    seed.py              config, providers, templates, input files
    wait.py              poll observable state
  test_batches.py        intake, routing, validation, approval
  test_dispatch.py       window, allowance, jitter, leases, retries
  test_replies.py        threading, DSN, attribution, suppression
  test_followups.py      derivation, threading, mixed content sources
  test_stats_retention.py
  test_backup_restore.py
  test_config.py
```

One shared harness, reused by every ticket. A ticket adds scenarios, never a second harness.
`uv run pytest` is the gate. Real-account checks below remain the final proof that the transport
and attribution are honest.

The software is still used by people against real accounts, on a real machine.

| Check | How |
|---|---|
| Transport | send to real addresses, read the result in the real mail client |
| Watchers | reply from a second mailbox, watch the count change in the TUI |
| Restart | `kill -9` during work, start again, look at what is queued and what is sent |
| Allowance | restart at the end of a day and confirm the counter did not reset |
| Failure | send to an address that rejects, read the reason in the Failures screen |
| Restore | back up, wipe the data directory, restore, compare the numbers |
| Auth | revoke the grant at the provider, confirm `needs_reauth` and the reconnect |

Setup lives in `tests/harness/`, not in ad hoc scripts. Fixtures write the input files, seed the
fake mailbox, start the daemon, and wait on observable state instead of sleeping. Every assertion
runs against the daemon's real HTTP responses, database, content store, or log file.

Unit tests are not part of the gate. A pure algorithm that cannot be reached from outside (thread
normalization, backoff arithmetic, DSN parsing) is exercised through the interface that uses it,
not through a private import.

The things worth checking by hand after any change to the pipeline, because they cause real harm:

- a recipient never receives two copies of one job
- a job never stays queued forever after a crash
- an allowance is never exceeded, including across a restart
- `last_uid` never advances past a message that was not stored
- a bounce is never counted as a reply

The token invariant is not tested at all. It is enforced structurally (see `04-security.md`): one
accessor, short-lived bearer tokens, and redaction at the logging boundary. Read the log after a
send and confirm for yourself.

## Code conventions

| Rule | Detail |
|---|---|
| Few comments | Python is readable. A comment is allowed only for a why the code cannot show, and it is one line. No TODO or FIXME in a file, ever: work lives in the plan or the issue, not in the source |
| Configuration over code | any limit, threshold, timeout, path, policy, or default a user might want to change belongs in the config schema. Structural constants (header names, MIME boundaries, protocol verbs) stay in code |
| Standard uv workflow | `uv init`, `uv add <package>`, `uv run <cmd>`. Never hand-edit the dependency table, never pin a version by hand, never write raw TOML for a package. Version selection is uv's job |
| Clarity over speed | write the obvious version. Do not micro-optimise, do not add a cache, do not reach for concurrency until a measurement says so. There is no performance target in this plan |
| Line length | `ruff format` with its defaults. No `[tool.ruff]` or `[tool.ruff.lint]` block: `ruff check --fix` and `ruff format` run on whatever their shipped defaults say, then the remaining findings are fixed by hand. No custom line length, no per-rule exclusions |
| Human code | standard library idioms, type hints where they help the reader, early returns, no clever one-liners that need decoding. If a line needs a comment to explain what it does, rewrite the line |
| Commits | one commit per ticket, after its live checks pass. Conventional type and scope, subject only: `feat(dispatch): add tick loop, allowance, leases`. Lowercase type, a comma separated list of what changed, under 72 characters. The subject says what changed; a body, if there ever is one, says why, never how. No footers, no `Co-authored-by`, no emoji, no long narrative |
| Logging | every ticket ships its own detailed events. One call site, two sinks: JSONL in `logs/downcroc.jsonl` for querying, and a pretty aligned colour line on a terminal. Structured fields, never formatted strings: `log.info("job.sent", job_id=..., account_id=..., recipient=..., duration_ms=...)`. No `print`, no bare `except` that swallows, no log line without the ids that let you follow it |

### Logging

The log is a product surface, not a debugging leftover. It answers "what did the daemon do, for
which account, in which batch, and how long did it take" without reading code.

One event, two renderings:

```
{"ts":"2026-10-22T14:03:11.812Z","level":"info","event":"job.sent","job":"job_01k8","account":"acct_gm","batch":"bat_01k7","duration_ms":412,"attempt":1,"recipient":"a@b.c"}
14:03:11.812  ok    job.sent        job_01k8  acct_gm  bat_01k7  412ms  a@b.c
```

Rules:

- The event name is dotted and stable: `job.sent`, `oauth.failed`, `restore.refused`. It is what
  you filter by, so it is never a free-form sentence.
- Every event carries the ids it touches and a duration when it crossed a boundary.
- Levels are honest: `info` for a completed unit of work, `warning` for something that changed the
  outcome, `error` for a failed attempt, `debug` for per tick noise that stays out of the default
  file level.
- Errors log the code and the fields, once, where the decision was made. They are not re-logged at
  every level of the stack.
- Credentials never reach the boundary. The redaction filter is the last line, not the only one.
- `downcroc logs` filters by event, level, account, batch, job, and time, follows live, and renders
  pretty on a terminal or raw JSON with `--json`. It reads the file, so it works with the daemon
  stopped.

Each ticket lists the events it introduces and the acceptance check that those events are both
queryable and readable.

These rules are not aspirational. A review that finds a `TODO`, a hand-pinned version, or a limit
hardcoded in a module sends the change back.

## What each phase deliberately omits

| Phase | Omitted on purpose |
|---|---|
| P0-P1 | any sending, any watcher. Prove the shell before the engine |
| P2 | threading quality. Store first, attribute later |
| P3 | batches. One message proves the transport |
| P4 | attribution. Sending is measured before replies are trusted |
| P5 | polish. Correct numbers matter more than a nice screen |
| P6 | features. Survive failure before getting faster |
| P7 | new surfaces. The web client is a later, separate build against the API as it stands then |

## After this plan

Two things are deliberately outside it and are re-opened only with a decision:

1. **A web client.** The API is built for it. Served from the same daemon, same events, static
   assets, no second execution path.
2. **Remote access.** Requires a token, a pairing flow, and a serious revisit of the loopback
   trust assumption in `04-security.md`.

# 11 - Decision log

Every decision taken during design, what was chosen, and why. Numbers are the question numbers
from the design conversation, kept so any decision can be traced back.

Three entries are marked **superseded**. They were answered, then revised later with better
information, and the later answer is the one in force.

## Product scope

**Q1 - Threat model.** Originally: a local user, plus the disk being stolen. Superseded in part by
Q22 and Q29: the live API is trusted on loopback, and the vault exists to protect credentials at
rest. The disk-stolen case still drives the vault.

**Q10 - What is downcroc?** Not a mail client, and not a composer. It orchestrates: send from your
own accounts, receive, attribute replies, watch threads. Drafting belongs in a real mail client.
This is why the TUI has no compose screen and why every input is a file.

**Q12 - LLM features.** Out. No model dependency, no data egress, no non-determinism in a pipeline
where a duplicate send is the worst outcome.

**Q15 - "Chains".** Resolved as threads: message-id based conversations, not a chain of batches.

**Q18 - Scale target.** About 1,000 jobs per day across about 10 accounts. This sets the whole
performance envelope: SQLite is enough, one process is enough, no queue server.

**Q25 - Vocabulary.** Account, attempt, batch, job, message, thread, watcher, reply, event, vault.
Fixed early so the schema, the API, and the UI agree.

**Q57 - Opt-out and unsubscribe.** Out of scope. This is personal outreach, not a marketing list.
No unsubscribe header, no suppression-by-request list beyond replies.

## Architecture and lifecycle

**Q3 - Daemon lifecycle.** First answer: explicit lock, process death means locked.
**Superseded by Q31**: an always-on service that starts locked and unlocks on demand.

**Q11 / Q22 - API surface and auth.** Loopback HTTP plus SSE. The original answer had no token,
no cookie, and no pairing. **Superseded for release 1 by Q71**: every route except public
health and the OAuth callback requires a per-run bearer token, and Host and Origin are
validated. The loopback assumption still holds for anything with the token file.

**Q19 / Q31 - Startup and stop.** The daemon starts locked, so it can start at boot. Unlock is a
separate human act. Stopping from the CLI locks, because the key only ever lived in memory.

**Q13 - Client order.** TUI first. The web client comes later, against the same API, with no second
execution path in the daemon.

**Q21 - Modularity.** Interfaces for providers and transports, declared providers in TOML, no
hardcoded Gmail branch. The user's constraint: rewriting code later is expensive, so pluggability
is bought now and paid for in three small interfaces.

**Q24 - Restart survival.** Everything behaviour-affecting is persisted. See the durability table
in `03-data-model.md`. No work exists only in memory.

**Q14 - Definition of done.** A full round trip at real scale: many accounts, 1,000 jobs, real
replies counted, a `kill -9` in the middle with no duplicate to any recipient, and a restore that
reproduces the same numbers.

## Storage

**Q5 / Q6 - Retention.** Jobs 30 days or 10,000 rows; events a 10,000 row ring buffer; hourly
activity 90 days; daily activity 730 days; logs 10 MB across 5 files. All configurable.

**Q59 - Statistics are stored.** Sent, failed, received, replies, bounces and suppressed are
written to hourly and daily activity tables and to per-batch counters, in the same transaction as
the event that causes them. Every one of them is queryable by account, batch, hour, day, and
range. The aggregates are rebuildable from `jobs` and `messages` while those rows survive, so they
are derived data with a source of truth rather than a parallel record that can drift. They are
kept far longer than the rows they summarise, because pruning a job must not erase the fact that
it was sent.

**Q60 - No hourly cap.** The daily allowance per account is the only quota. There is no hourly
limit, no global ceiling, and no burst guard. Hourly rows are recorded for observation only, so
the shape of a day is visible without any number quietly throttling you. The available controls
are the daily allowance, the active window, the jitter range, and disabling an account.

**Q16 / Q44 - Where jobs come from.** A file drafted elsewhere: JSON array of recipients, or CSV
plus a template. Batch source is copied into the content store at submit. The database holds the
path, the hash, and the metadata, not the document.

**Q20 - What is encrypted.** Credentials only. Mail bodies are plaintext in SQLite, because they
are queried constantly and the vault password is not a substitute for disk encryption. Stated
rather than implied.

**Q48 - Storage split.** Batches and templates are files. Mail is in the database. This follows use:
one is read once at send, the other is joined on every screen.

**Q52 - Mail retention.** 90 days by default, configurable per account.

**Q53 - Attachments.** Never blobs in the database, and that includes inline images. Every file
part, whether a PDF or an image referenced by `cid:` in an HTML body, is written to the content
store on disk, with hash, size, content type, and path in its row. The database stores metadata
and never binary payloads.

**Q49 - Snapshots.** The batch is snapshotted and hashed at submit, so editing the original file
changes nothing and the provenance is provable.

**Q35 - Versioning.** Forward-migrate only, and a newer bundle is refused by an older binary with
both versions named. No downgrade path.

**Q30 - Backups.** A bundle contains everything: database, content, config, templates, vault,
failure log. Excludes only the vault password, runtime state, and logs by default.

**Q34 - Per-account limits.** Daily allowance, active window, hourly activity, jitter range, job bound
to account. **Partially superseded by Q43**: accounts are active by default; there is no daily
activation step.

## Sending

**Q7 - One job per recipient.** Never a shared `To`. Every recipient is independently sendable,
retryable, and attributable.

**Q8 - Rate limits.** User-configured, not hardcoded. The daemon does not guess provider limits and
does not silently clamp a user's number.

**Q40 / Q47 - Account selection.** Random among eligible accounts, weighted by remaining daily
allowance. Eligibility is: enabled, connected, inside its window, allowance remaining.

**Q41 - Jitter.** Per account, a min and a max in seconds, uniform between sends. Configurable per
account because different accounts have different tolerances.

**Q42 / Q46 - Scheduling.** The queue drains a daily bucket. There is no send-at-a-time feature and
no delivery-time promise. `not_before` exists as a floor on a batch, not as a schedule, and has no
UI in the first client.

**Q43 - Always active.** Accounts participate by default. Enabling and disabling is a manual toggle,
not a daily ritual.

**Q39 - Account binding.** Bound at creation. Movable while `queued`, refused once a lease is held,
because the message may already be on the wire.

**Q50 - Batch format.** One JSON document containing an array of recipients. A wrapped object with
batch metadata is also accepted, because a bare array cannot carry a template name.

**Q55 - Dry run.** Five random rendered samples. Approve one, which sends immediately, then check
it in the real inbox, then approve the rest. Sample job recorded so it cannot be sent twice.

**Q58 - Retries.** Five attempts, exponential backoff with jitter, transient failures only. Permanent
failures go to `failed.jsonl` with a TUI notification, a counter, and a retry action.

**Q32 - Suppression.** Automatic, from confirmed replies, per account, switchable per batch. Per
account because two accounts may legitimately write to the same person.

**Q33 - Follow-ups.** First-class batches, thread-linked, default recipients are the original
recipients who have not replied. They inherit the parent's account so the thread stays in one
mailbox.

## Inbound

**Q17 - Mailbox browsing.** A full read-only INBOX browser, primarily so reply counting is
verifiable rather than a number you have to trust.

**Q26 - Reply headline.** `41 inbound (37 replies)`. Total with confirmed in brackets, because it
shows both the catch-all and the precision attached to it.

**Q27 - Granularity.** Per batch, drillable to recipient, thread, and message.

**Q28 - Bounces.** DSNs are classified separately and never counted as replies. A bounce does not
change a `sent` job to `failed`; the remote server rejected it after we sent it.

**Q36 - Folder scope.** INBOX only. No spam folder handling, no flagging. The missed-reply cost is
disclosed in the UI.

**Q37 - Reply window.** 60 days by default, per batch. Late replies still attach and still count for
suppression; the window only separates them in statistics.

**Q56 - Watchers.** Every connected account is watched, individually toggleable. One IDLE thread per
account, read-only, never marking read.

## Security

**Q29 - The token invariant.** Tokens are the crown jewel. No API response, event, log line, or
error message ever contains one. Local access is accepted as copy-level harm: someone with your
machine and your unlocked session can read your mail, which is bad but recoverable, unlike a leaked
refresh token.

**Q38 - Checks on the invariant.** Originally untested and enforced structurally: one accessor,
short-lived bearer tokens, and redaction at the logging boundary. Release 1 adds authentication
and leak tests that scan logs, API errors, and backup bundles for the daemon token.

**Q4 / Q22 - Explicitly accepted risk.** The original loopback API was unauthenticated.
**Superseded for release 1 by Q71**: the API now requires a per-run bearer token, and the
remaining same-user risk is recorded in `04-security.md` rather than treated as an oversight.

## Client

**Q54 - TUI framework.** Textual. Async, keyboard-first, good tables, and it does not look like a
web app in a terminal.

**Q23 - Config editing.** `config.toml` is the only source of truth. The TUI reads and writes through
the API, which validates and rewrites atomically and hot-reloads. Two stores never disagree.

**Q45 / Q51 - Templates.** Files on disk, edited through the TUI by handing off to `$EDITOR`. The TUI
collects paths and previews renders; it never becomes the document store.

## Decisions taken while writing this plan

These were not asked. They are engineering necessities or judgement calls, listed so they can be
challenged individually.

| Decision | Why | Where |
|---|---|---|
| Sent-folder reconciliation for `sending` rows | SMTP has no idempotency; the alternative is silent duplication | `03`, `06` |
| Leases with expiry on `sending` jobs | a killed daemon must not strand work | `03` |
| One event ring buffer in SQLite | resumable SSE without a separate broker | `02`, `03` |
| Events carry ids, not objects | prevents two representations of one record drifting | `02` |
| `failed.jsonl` plus a table | portable durable record plus a query surface | `03`, `06` |
| Capability declarations per provider | so the UI can say "polling", not lie about "live" | `05` |
| Sent-folder probe with fallback names | reconciliation must work across servers | `05` |
| Restore staged through a pending marker | the destructive step must not live in a retryable request | `09` |
| No automatic backup by default | writing a copy of all mail somewhere unasked is not a safe default | `09` |
| Sanitize HTML at render, not at store | the stored copy is evidence | `07` |
| Read-only posture on the remote mailbox | makes it safe to point at a primary account | `07` |
| `app_version` and `schema_revision` both in the manifest | version refusal needs both to be meaningful | `09` |
| Per-account send policy stored on the account row | each account differs, the account API edits one at a time, and dispatch reads policy in the same query; `[sending]` supplies the defaults | `01`, `03` |

## Code and workflow

**Q61 - Comments.** Almost none. Python is readable; a comment only earns its place for a why the
code cannot show, and it is one line. No `TODO` or `FIXME` in source at all: work belongs in the
plan or the issue, not in a marker nobody reads.

**Q62 - Configuration over code.** Every limit, threshold, timeout, path, and policy a user might
want to change lives in the config schema with a default. Structural constants (header names, MIME
boundaries, protocol verbs) stay in code. This is the TOML-is-truth decision applied inside a
module.

**Q63 - No test suite.** Testing is live, against a running daemon, by real testers. No pytest
tree, no fake protocol servers gating a build. Setup scripts in `scripts/` print and do not assert.
A self-check script is acceptable only where observing the behaviour live is genuinely impractical.

**Q64 - The standard uv workflow.** `uv init`, `uv add <package>`, `uv run <cmd>`. Dependencies are
never written into the dependency table by hand and versions are never pinned by hand; uv resolves
them and the lock is committed.

**Q65 - Formatting.** `ruff check --fix` and `ruff format`, both on the tool's own shipped
defaults. No `[tool.ruff]` block and no custom line length: the tool decides, and the remaining
findings are fixed by hand.

**Q66 - ORM and migrations.** SQLAlchemy 2.0 declarative models, Alembic for migrations, both only
inside `store`. Migrations are generated with `alembic revision --autogenerate`, reviewed, and
corrected before they are applied; `render_as_batch=True` because SQLite cannot alter most things.
The ORM owns the schema so there is no second definition of a table, and repositories return
domain objects so SQLAlchemy never leaks into `core`.

**Q67 - The daemon is the source of truth.** The OpenAPI document is generated by FastAPI from the
routes and schemas, and the client is generated from that document with `openapi-python-client`,
committed and regenerated as a mechanical step. The prose in `02-api-contract.md` explains the API
rather than defining it, and changes whenever the build teaches us something. Nothing is frozen.

**Q68 - Commits.** One commit per ticket, made after its live checks pass. Conventional type and
scope, and a subject that lists what changed: `feat(vault): add key derivation, sealed store`.
Short, plain, no footers, no co-author line, no emoji. The subject says what changed, and a body
would say why rather than how. No long narrative.

**Q69 - Vault details settled while building.** `vault.enc` is magic, version, KDF parameters,
salt and nonce, an unkeyed SHA-256 digest, then AES-256-GCM ciphertext with the header as AAD.
The digest only separates accidental damage from a wrong password; it is not a security
boundary. The lifecycle lives in `core/vault/service.py`, the format and crypto in `vault/`.
Throttling is configurable in `[vault]`: five free attempts, then a delay from one second that
doubles to a five minute cap. A successful unlock resets the count; a corrupt file does not
count. First unlock creates the vault, a second unlock returns `vault_already_unlocked`, and a
second lock is a no-op. Chosen KDF parameters live in the header, so a vault opened on a slower
machine keeps its original cost.

**Q70 - Connect details settled while building ticket 04.** Providers are declarations, not
branches. Built-ins ship in `providers/declarations/`; `providers.toml` holds `[providers.<id>]`
overrides; `providers.d/*.toml` holds complete declarations. They merge in that order, so the
dropped files win. Unknown fields are refused at startup rather than ignored, and a provider file
with group or other permissions is chmodded to `0600` with a `provider.permissions` warning. The
OAuth client id is provider configuration; the optional client secret sits beside it at `0600`
and is never in the vault or an API response. OAuth URLs must be `https` unless the host is
loopback, which exists for a local test server. The loopback callback binds `127.0.0.1` on an
ephemeral port, checks the state nonce with `hmac.compare_digest`, and uses PKCE S256 with the
verifier in memory only. Attempts are persisted rows with one pending attempt per account, a TTL
from `[connect]`, a clean shutdown reason of `daemon_stopped`, and a startup reason of
`daemon_restart`. The token manager caches the access token and its expiry in the vault, refreshes
under a per-account lock with a configurable margin, and treats `invalid_grant` as
`needs_reauth` while network and other provider errors leave the status alone. IMAP XOAUTH2 is
built by `imap-tools`; there is no second SASL implementation. Plaintext IMAP is allowed only on
loopback. A password account connects through `POST /api/accounts/{id}/connect`, stores its
password under `<account>:app_password`, and never echoes it.

**Q71 - Portable lifecycle and the control token.** Release 1 runs on Linux and Windows. Paths
resolve from XDG on Linux and from `APPDATA` and `LOCALAPPDATA` on Windows. POSIX permission
bits are applied on Unix; Windows
uses the user profile ACL. The instance lock is `fcntl.flock` on POSIX and `msvcrt.locking` on
Windows, and process liveness is `os.kill(pid, 0)` on POSIX and `OpenProcess` plus
`GetExitCodeProcess` on Windows. Detached start uses `start_new_session` on POSIX and the
Windows detached process flags. `downcroc service stop` does not signal the process: it
authenticates `POST /api/service/stop` with a per-run token in `daemon.token` (32 random
bytes, mode `0600` on Unix and an owner-only ACL on Windows, removed on clean stop), and the
endpoint sets Uvicorn's shutdown flag so the normal application lifespan locks the vault and
releases resources. A hard kill drops the OS lock and the next start replaces the stale
`service.json` and rotates the token.

**Q73 - Full API authentication.** Release 1 extends that token to every API route
except `GET /api/health` and the OAuth callback, which keeps its state nonce. The CLI reads the
token automatically, so existing commands do not change. Requests must present a trusted
loopback Host and, when present, a loopback Origin. `/docs`, `/redoc`, and `/openapi.json` are
disabled; `downcroc openapi` generates the document in process. `downcroc auth status` reports
state and token acceptance without printing the secret. There is no browser login, cookie,
pairing flow, or GUI session. The full suite runs on a Linux and Windows GitHub Actions
matrix; packaging and binary builds stay in CI. macOS is out of scope for release 1: no CI
leg, no artifact, no support commitment.

**Q72 - Packaging and licensing.** Release 1 ships as an Apache 2.0 wheel and source distribution
built with `uv_build`. Alembic migrations and the provider declarations live inside the
`downcroc` package and are loaded from package paths, so an installed wheel never reaches back
to the repository root. The project version is the wheel version; `downcroc --version` reads it
from installed distribution metadata. `LICENSE` and `NOTICE` are maintained by hand;
`THIRD_PARTY_NOTICES.md` is generated from `uv.lock` plus installed package metadata and checked
in CI. Provider declarations are maintained by hand, migrations are generated by Alembic, and
dependency versions are uv-managed. All three legal files are declared as licence files, which
puts them in both artifacts and in the installed distribution metadata. Wheels are built and
smoke-tested only in the Linux and Windows CI matrix; the developer workflow stays on
`uv run` and never builds a wheel locally.

**Q74 - Native user services.** `downcroc service install` writes a systemd user unit under
`XDG_CONFIG_HOME/systemd/user` (or `~/.config/systemd/user`) or a Windows scheduled task XML in
the state directory registered with `schtasks /Create /XML`. The definition runs the absolute
launcher path with `serve`, keeps `HOME` and any XDG overrides in the service environment,
uses the home directory as the working directory, and supervises at user level only:
`systemctl --user` or `InteractiveToken` with `LeastPrivilege`. Install stops a detached daemon
first, then reloads and starts through the manager. Reinstall overwrites the same definition,
so no duplicate service appears. Uninstall stops the service and removes only its definition;
config, data, and state stay. `service install --print` emits the definition and command plan
for inspection. CI checks the generated systemd unit and task XML. Actual registration is a
manual release smoke check because hosted runners do not provide a reliable per-user service
manager.

**Q81 - The vault password may live in the system credential store.** Typing a second password
forever is the main reason a personal mail tool gets abandoned, so `vault init` offers to keep
the master password in the operating system credential store: Secret Service on Linux, Windows
Credential Manager on Windows. The user then remembers only the password they already use to
log in. The store holds the password itself, not the derived key, and only the CLI reads it;
the daemon keeps its invariant that it starts locked and receives an unlock over the API. The
choice is opt-in, off by default under `--no-input`, removable with `vault keyring disable` or
`vault lock --forget`, and reported in `vault status` and `doctor`. File and plaintext backends
are refused, because a second password to protect the second password defeats the point. The
security trade is documented in `04-security.md`: while the store is enabled, any process in
the same user session can unlock, so the boundary is the OS login and disk encryption, not the
vault password. That was already true of a running daemon, and the convenience is what makes
the product usable.

## Deliberately deferred

| Deferred | Trigger to revisit |
|---|---|
| Web client | after P7, against the API as it stands then |
| Remote access with a token and pairing | a real need, plus a decision to reopen the loopback assumption |
| Publishing the Google OAuth client | when seven-day token expiry becomes intolerable |
| Scheduled send at a specific time | when bucket drain is proven insufficient |
| Opt-out and unsubscribe handling | if this stops being personal outreach |
| Spam folder ingestion | if missed replies become a measured problem |
| Multiple users | not a product direction |
| Mail-body encryption at rest | if the disk threat model changes |
| Attachments in outgoing mail, richer than declared files | when the first real template needs them |
| A second transport for sending, such as an API send endpoint | only if SMTP becomes a bottleneck |

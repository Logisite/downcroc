# 13 - Interactive CLI, help, and the input contract

Status: proposed for release 1. This is the design for ticket 09 and its dependants.
It records both what is wrong today and what replaces it. Nothing here is implemented yet.

This file supersedes `08-tui.md` for release 1. The Textual application described there is
deferred; release 1 is CLI only, with a human interactive layer built on prompts. `08-tui.md`
stays as the design for a later graphical client. The API remains the only surface any client
speaks, so that work is not wasted.

Related tickets: 09 (this file), 04 (docs, blocked on 09), 06 (binaries, needs the frozen
launcher prefactor), 07 (installers, needs `downcroc update`), 08 (release, needs all of them).

---

## 0. Why this file exists

The daemon is finished and tested. The CLI in front of it is a thin flag surface written for
scripts, and it is being asked to serve as the only human interface of a 1.0 product. It does
not do that today. It misleads in specific, reproducible ways, and it gives no path through a
feature for a person who has not read the source.

The request that produced this document, in the user's words: "it doesn't give a schema for
the inputs it needs, if I want to send an email I don't know the format, do I need to curl to
do that? What is the clear user flow, is there a clear TUI path for the user flow per feature
or is it all a chain of flags."

This file answers that question three ways:

1. An exhaustive audit of every place the CLI lies, dead-ends, or hides a capability.
2. A concrete human flow for every feature, expressed as prompts and menus over the same
   handlers the flags call.
3. A complete, discoverable input contract, with schema, examples, offline validation, and
   template tooling, so that sending mail never requires reading `plan/` or using curl.

The audit started from the source and from the ticket text. It was then checked against an
independent black-box report, `.scratch/downcroc-cli-ux-report.md`, produced against a running
`1.0.0rc1` with no source access. That report found 4 blocking, 11 high, 14 medium, and 8 low
issues. Every one is mapped to an identifier in section 3.15, including the three places the
report is mistaken or unconfirmed. Nothing from the report was dismissed without a code check.

---

## 1. Scope

In scope:

- Interactive prompts and menus for humans on a TTY.
- A help system with command help, topic help, and an interactive help screen.
- Discovery and validation of campaign inputs, templates, and batch operations.
- Truth fixes in output, exit codes, error rendering, provider reporting, and path handling.
- The frozen-launcher fix that ticket 06 depends on.

Out of scope:

- Any TUI or browser UI. No Textual, no web client, no GUI login.
- macOS. Release 1 ships and is tested on Linux and Windows only: no CI leg, no artifact, no
  installer, and no support commitment. The darwin fallbacks stay in the code but are untested.
- New daemon capabilities that are not required for truth. Account policy editing, for
  example, has no API route and is deferred (see section 23).
- Changing the flag interface. Every existing flag keeps its name and meaning, except where
  the flag itself is a lie (section 3.1, D6 and D7), and those changes are called out.
- Shipping a shared OAuth client id. Gmail's OAuth door needs a client id and secret supplied by
  the operator (D46). The app-password door needs neither. The CLI offers both and states the
  cost of each, rather than pretending only one exists.

The flags stay the complete agent and script interface. The interactive layer is a front end
over the same command handlers. There is no second behaviour path that only the menu can
reach.

---

## 2. Principles

**P1. One handler per action.** A menu item and its flag call the same function. If the menu
can do it, the flag can do it. If the flag cannot do it non-interactively, the menu must not
either.

**P2. Flags are the contract.** Agents, cron, and CI use flags only. Prompting is an
additional front end, never a requirement.

**P3. Prompt only on a real TTY.** No prompt when `--json`, `--no-input`, `--yes`, stdin is
not a TTY, stdout is not a TTY, or `CI` is set. In those modes, missing input is an error that
names the flag which supplies it. A command must never hang waiting for a person who is not
there.

**P4. Never lie.** Every number, state, path, and hint shown to a person is true, or is
labelled as an estimate. Absence is reported as absence, not as silence. A command whose job
is to report health must fail when health is bad.

**P5. Content is visible by default.** No prompt, menu, or help screen hides text behind an
animation, a pager, or a color. Long output is paged only when interactive, and paging is
opt-out.

**P6. The product teaches its own contract.** A person must be able to discover the input
format, get a working example, validate it, and fix every error without leaving the CLI and
without a running daemon.

**P7. Destructive actions are named, counted, and confirmed.** Every action that deletes,
overwrites, sends, cancels, or restores shows what will change and asks once. Scripts get
`--yes`; the prompt is not a substitute for the flag.

**P8. Secrets never transit the screen or the log.** Passwords use a masked prompt or
`--password-stdin`. No secret appears in argv, help output, errors, events, or examples.

**P9. The interactive layer owns no state.** It reads from the daemon, writes through the
daemon, and keeps nothing between runs except the draft files it deliberately writes.

**P10. One vocabulary.** The words in the UI are the words in the docs and in the API. Where
a domain word is unavoidable (`reply_state`, `uidvalidity`), the UI explains it once and links
to the glossary.

---

## 3. Audit: every place the CLI misleads

Each entry has an identifier, the evidence, the impact on a person, the fix, and the phase
that fixes it. Phases are defined in section 19.

Severity: **S1** blocks a feature or destroys data, **S2** actively misleads, **S3** hides a
capability or wastes time, **S4** rough edge.

### 3.1 Blocking and data-affecting defects

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D1 | S1 | `account connect` always prompts for an app password, regardless of the provider's auth kind | `cli/commands/accounts.py::_password`; `core/accounts_service.py::connect_password` rejects every provider whose `auth_kind` is not `app_password` | A Gmail or Microsoft user on the OAuth door follows the only offered path and hits a dead end, and the server hint that explains it is dropped (D2) | Read `auth_kind` before prompting. For `app_password`, prompt and verify (section 6.3.1). For `oauth2`, start an attempt and explain the client id and secret. For `none`, connect without a secret | A |
| D2 | S1 | The CLI discards every server `hint` and `details` field | `cli/client.py::_raise` forwards only `message` and `fields`; `api/errors.py` emits `hint`, `details` | The most useful sentence the daemon produces never reaches the user: "start an oauth attempt instead", "connect the account first", "restart the daemon to issue a new token" | Render `hint` on its own line and a compact `details` block. In `--json`, emit the whole envelope | C |
| D3 | S1 | `restore` replaces the data directory with no preview and no confirmation | `cli/commands/restore.py::run` validates, requests, and swaps before printing anything | An operator restores the wrong bundle, or restores when they meant to back up. There is no undo | Print the bundle manifest (created at, revision, counts, size, files), state what will be replaced, require a typed confirmation or `--yes`, and only then request the restore. Add `--dry-run` to stop after the preview | C |
| D4 | S1 | First-run vault creation takes one hidden prompt, so a typo becomes the permanent password | `cli/commands/vault.py` unlock path | The vault is unrecoverable and the installation is lost | Prompt twice, compare, and re-prompt on mismatch. Warn that the password cannot be recovered. `--password-stdin` stays single-shot for scripts and is documented as such | A |
| D5 | S2 | `auth status` always exits 0, even when the token is rejected or the daemon is unreachable | `cli/commands/auth.py::run` returns 0 unconditionally | A script or health check treats a broken token as healthy | Exit 1 when `accepted` is false or state is `unreachable`/`stale`. Add `--json` (already present) and document the exit contract | C |
| D6 | S2 | `job create` writes jobs into a batch named `manual` that no batch row backs | `core/outbound/service.py` default `batch_id="manual"`; `/api/batches/manual` is 404 | The job appears in `job list`, but `batch show manual`, `batch list`, and stats disagree. The user cannot find or cancel the group | Create a real one-message batch through the campaign path for `job create`, or register a real batch row. Preferred: route guided and flag sends through a draft campaign and let `job create` keep its escape hatch only with `--batch` naming an existing batch | C |
| D7 | S2 | `batch submit --approve one` does not approve: it releases one job and sends it immediately | `cli/commands/batches.py::run`, `core/batches/service.py::approve("one")` | A person reading "approve one" expects a sample held for inspection, not an immediate send. On an `auto` campaign the batch is already sending and the flag fails | Rename the meaning in help and prompts: `--release-one` sends one sample now, or keep `--approve one` but document and prompt it as "send 1 sample now". Reject the flag with a clear message when the campaign is `auto` | A |
| D8 | S2 | `batch submit --approve all` silently sends the entire campaign at submit time | same as D7 | A person who meant "queue it" sends 10,000 messages | Keep the flag for agents. The interactive flow asks "submit and hold" versus "submit and send" in words, and never defaults to send | A |

### 3.2 Misleading output

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D9 | S2 | Every human value is cut at 48 characters, in tables and in the key/value view, with no indication of how much was lost | `cli/output.py` `MAX_CELL = 48`, used by `cell()` for both `table()` and `record()` | Long subjects, error messages, paths, and provider notes are silently mangled. `job show` can clip the failure reason | Truncate only free text, widen with `--wide`, add `--full` for records, always show IDs, addresses, and codes in full, and append a dimension hint (`... 214 chars`) instead of a bare ellipsis | C |
| D10 | S2 | `batch preview` reports the sample size as the message count | `cli/commands/batches.py::_preview` prints `len(preview["messages"])`; the daemon samples `intake.sample_count` (default 5) | A 10,000-recipient campaign reads "messages 5". A broken 5-row campaign looks identical to a valid 10k one | Preview returns and prints `total`, `sampled`, `valid`, `warnings`, routing counts, and follow-up steps. Sample remains 5 unless `--all` | C |
| D11 | S2 | `account providers` prints fiction | `cli/commands/accounts.py::_providers` prints `oauth_configured` under the header `oauth`; `generic` shows empty hosts as `:993` and `:587` | Gmail shows `auth oauth2` beside `oauth False` with no explanation. `generic` looks usable and is not. The provider `notes` field is never shown | Replace the column with `door` (`OAuth client` or `app password`) and compute `ready` per door. Hide empty hosts. Show the `notes` line under the table. Mark generic as "requires hosts" when they are empty. Section 15 has the table | C |
| D12 | S2 | Bare `downcroc` prints "start it with: downcroc service start" whenever status returns 0, including when the daemon is already running | `cli/main.py` fallback | The only advice a first-time user gets is wrong half the time | Bare command becomes state-aware on a TTY (section 6.2). Non-interactive bare command prints the state and the correct next command | A |
| D13 | S2 | `logs` prints nothing and exits 0 when the log file does not exist, including when the daemon was never started | `cli/commands/logs.py` | A wrong `XDG_*` directory, a daemon under another user, or a daemon that never ran looks exactly like a quiet log | Say `no log file at <path>` and exit 1. If the daemon is also stopped, print the daemon-down hint. In `--json`, emit `{"events": [], "log_file": "<path>", "exists": false}` | C |
| D14 | S2 | FastAPI request-validation errors call everything a request body, including bad query parameters | `api/errors.py` builds `"the request body is not valid"` for every `RequestValidationError` | `--limit 501` or a bad `--from` produces a message about a body the user never sent | Derive the message from the error locations (`query`, `path`, `body`) and name the offending parameter. This is an API change and a CLI rendering change | C |
| D15 | S2 | `mail attachment` overwrites an existing file without a word | `cli/commands/mail.py::_destination`, `Path.write_bytes` | Silent data loss in the download directory | If the target exists, prompt (interactive) or fail with `use --force` (non-interactive). `--force` overwrites. `-o DIR` writes into the directory using the server filename | C |

### 3.3 Dead ends and missing human paths

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D16 | S1 | There is no human path to send mail. `batch submit` requires a file whose format is undocumented inside the product | `cli/parser.py`, `core/inputs/*`, no schema or example command | The flagship feature is unreachable without reading the repository. This is the user's core complaint | Add `send` (guided), `batch schema`, `batch example`, `batch validate`, `batch submit --dry-run`, and `template list|new|show|validate`. Document the format in help and in `plan/` | B |
| D17 | S1 | The input contract is undiscoverable: two JSON shapes, CSV header rules, template layout, follow-up schema, attachment rules, and limits exist only in source and `plan/` | `core/inputs/campaign_input.py`, `csv_input.py`, `templates.py`, `campaign_message.py` | A person cannot know that `to` is an object with `email`, that `key` defaults, that a CSV needs `email`, or where templates live | Publish one contract from one registry, render it as help, JSON, and JSON Schema, and generate the docs from it (section 9, 10) | B |
| D18 | S2 | `--template`, `--step`, `--key`, and `--approve` have no help text, and there is no command to list templates or step ids. `batch preview` accepts `--key` but `batch submit --help` does not, so an idempotent retry is undiscoverable | `cli/parser.py` flags without `help=` | The follow-up and template features are effectively hidden, and a retried submit duplicates a batch | Add help text to every flag, including `--key` on `submit`, with the same wording as `preview`. Add an `epilog` with examples, `template list`, and `batch show` printing step ids | B |
| D19 | S2 | `account attempt --wait` sits silent for up to three minutes | `cli/commands/accounts.py::_wait` polls with no output | The tool looks hung, and a person kills it | Print the URL, say it is waiting, print a progress line every few seconds with elapsed time, and print the account state on each change. `--no-wait` is already the default; keep it | A |
| D20 | S3 | There is no single screen that answers "is it working and what needs me" | no `status` or `doctor` command | A person must run `service status`, `auth status`, `vault status`, `account list`, `stats summary`, and `failed list` and combine them mentally | Add `status` (short, current state) and `doctor` (checks with pass/fail and fixes) | C |

### 3.4 Silent clipping and missing data

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D21 | S2 | Every list is silently clipped at `limit` with no total and no continuation hint | list routes return bare arrays; CLI prints rows and stops. Only `batch show` warns about hidden recipients | A person believes there are 100 jobs, not 12,000 | Add `offset` where missing and an `X-Total-Count` response header. CLI prints `showing 1-100 of 12,043, use --offset`. `--json` exposes the total via the same header or a documented envelope | C |
| D22 | S2 | `--json` is promised broadly but missing on `account delete`, `backup`, `restore`, and `mail attachment` | `cli/parser.py` | Scripts cannot parse those commands, and error handling differs between commands | Add `--json` to each, including a JSON error object on stderr | C |
| D23 | S3 | `mail show` does not mark truncated bodies beyond a bracket; `record` clips values; there is no `--full` | `cli/output.py`, `cli/commands/mail.py` | A person cannot read a full subject or failure reason, and may miss that a body was truncated at intake | `--full` disables cell truncation for the command, `--wide` widens tables, and truncation always prints the original length | C |
| D24 | S3 | `service status` prints a clipped service path and no readiness detail | `cli/commands/service.py`, `output.cell` | Debugging a wrong unit path is guesswork | Show the full path under the summary, plus whether the definition is installed, whether the process is alive, and whether health answers | C |

### 3.5 State and path defects

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D25 | S2 | The daemon resolves relative input paths against its own working directory, not the caller's | `core/batches/source.py::_read_source`; `batch submit` sends `str(args.path)` | `downcroc batch submit campaign.json` fails or reads a different file depending on how the daemon was started | The CLI resolves every path to an absolute path against the caller's cwd and expands `~` before sending. The daemon keeps its own resolution for API callers | C |
| D26 | S2 | Path handling is inconsistent: `backup` expands `~` and detects directories; `restore`, `batch submit`, `batch preview`, and `job create --text-file` do neither, and a failed `job create --text-file` read prints a raw Python errno | `cli/commands/backup.py::_target` versus the others; `cli/commands/jobs.py` reads the file directly | The README example only works because of a trailing slash. A directory is treated as a file, and a missing input leaks `[Errno 2]` instead of an error code | One path helper in `cli/paths.py`, used by every path flag: expand `~`, absolutise, accept a directory where a generated filename makes sense, and return `input_unreadable` with the field and absolute path on a read failure. Document per command. Also D64 | C |
| D27 | S2 | `service start` cannot work from a frozen binary | `runtime/service/lifecycle.py` spawns `[sys.executable, "-m", "downcroc", "serve"]`; `units.launcher()` already handles `sys.frozen` | Ticket 06 would ship a binary whose `service start` fails | Use `launcher()` plus `serve` in `lifecycle.start`. Prefactor for 06, with the real proof in the binary smoke test | P |
| D28 | S3 | `batch submit` accepts `--template` with a JSON campaign and fails deep in the parser; `--step` is required for follow-up with no way to list steps; `--template` accepts only a bare name, never a path, so a file at an absolute path is rejected as an invalid name | `cli/parser.py`, `core/inputs/campaign_input.py`, `core/inputs/templates.py` | Errors arrive late and do not name the conflict. A template held outside `<config>/templates` is unusable even though the error says "template" | Validate the combination in the CLI and the daemon before reading the file, with a field-specific message. `--template` accepts a name or a path; a path is resolved and read directly. Reject `--template` with a JSON source, and `--step` without follow-up steps, at parse time. List step ids in `batch show` | B |

### 3.6 Provider truth

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D29 | S1 | The Gmail OAuth door cannot connect because `oauth_client_id` and `oauth_client_secret` ship empty, and nothing tells the user there is a second door | `providers/declarations/gmail.toml` | The most common provider either dead-ends on the OAuth path with no in-product explanation, or is written off entirely because the app-password path is not offered | Provider readiness per door in `account providers`, `account add`, and `doctor`. `account add` asks which door with no default, states both costs, and names the file and both keys for OAuth. The app-password door connects today | C |
| D30 | S2 | `account add` requires `--provider` and `--address` with no prompt and no provider list | `cli/parser.py`, `cli/commands/accounts.py::run` | A human must guess provider ids | Interactive picker with labels, readiness, and descriptions; flags unchanged | A |
| D31 | S3 | Account quota, window, and `max_in_flight` are displayed but not editable, and no API route exists | `domain/accounts.py`, `cli/commands/accounts.py::_show` | The numbers look like settings and are not | Label them read-only in release 1 and say where the limit comes from. Do not add an API route in 09 (see section 23) | C |
| D48 | S2 | `smtp_auth_mechanism` is declared, validated, and published by the API, but the sender never reads it | `providers/registry.py` validates it against `XOAUTH2` and `PLAIN`; `api/schemas/accounts.py` exposes it; `mail/smtp/sender.py::send` branches on `auth_kind` alone | A user edits it to fix a provider and nothing changes. It is a setting that does nothing | Honour it in the sender, or stop publishing it. Release 1 stops publishing it and keeps the field for a later provider that needs it | C |
| D49 | S2 | The Gmail guidance says only `oauth_client_id` is needed, but Google's token exchange also requires `oauth_client_secret` | `providers/oauth/client.py` sends the secret only when present; `gmail.toml` `notes` says "Set oauth_client_id in providers.toml" | A user follows the note, finishes the browser step, and the exchange fails at the last moment with `invalid_request` | Ask for and document both values, and make readiness require both. The prompt collects the pair | C |
| D50 | S1 | There is no way to configure a provider from the CLI. `account providers` mentions `providers.toml` only inside a JSON `notes` string, `config schema` has no provider fields, and the server hints that do name the file are dropped by the client (D2) and never give an absolute path or the key | `cli/commands/accounts.py::_providers`; `cli/commands/config.py::schema`; `providers/registry.py` and `core/accounts_service.py` emit `add it to providers.toml or providers.d`; `cli/client.py::_raise` discards it | The first real task, connecting a mailbox, cannot be completed. `generic` is the only provider that could work without an external registration and it has no hosts, so every provider dead-ends | Add `provider list|show|add|edit|remove` over the same registry merge path, render readiness from section 15, and make every provider error name the absolute file, the TOML section, and the key. `provider add` writes mode `0600` and never writes a secret | A |
| D51 | S1 | `account add` accepts only `--provider` and `--address`, so a `generic` account is created in a state that cannot connect, and an OAuth account cannot receive its client id | `cli/parser.py`, `cli/commands/accounts.py::run` | The workaround is hand-editing TOML, which the product does not mention at the point of failure | Add `--imap-host`, `--imap-port`, `--imap-security`, `--smtp-host`, `--smtp-port`, `--smtp-security`, `--username`, `--oauth-client-id`, and `--oauth-tenant`. Validate locally, refuse to create an account that cannot connect unless `--allow-unconnectable` is passed, and offer `provider add` in the error hint. The OAuth client secret is never a flag: it is prompted, or read through `--password-file`, then written to `providers.toml` with mode `0600`. App passwords go to the vault | A |

### 3.7 Jargon and discoverability

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D32 | S3 | Raw domain words are printed with no legend: `reply_state` (`confirmed`, `probable`, `late`, `bounced`), `credential: no`, `attempts_left`, `retry_after_s`, `uidvalidity`, `in_flight` | `cli/commands/mail.py`, `accounts.py`, `output.py` | A person cannot tell `probable` from `confirmed`, or that `credential: no` means "not authenticated" | Add a glossary topic, rename display labels (`credential` becomes `signed in`), and show state explanations in `account show`, `mail show`, and `job show` where the value is ambiguous | C |
| D33 | S3 | `downcroc -h` is argparse's bare list. Most flags have no help text. There are no examples and no topics | `cli/parser.py` | The help system documents nothing, which is the same as having none | Section 8. Every flag gets help, every command gets an example epilog, and topics cover concepts | B |
| D34 | S3 | The README advertises an unreleased wheel filename, no installer section, and `--json` on commands that lack it | `README.md` | A reader follows instructions that cannot work | Fix in ticket 04 against the shipped artifacts. Until then, README carries a one-line "release 1 is not published yet" note | 04 |

### 3.8 Interaction-specific defects

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D35 | S2 | `account delete` is the only destructive action that confirms, and it only does so on a TTY. `restore`, `batch cancel`, `failed retry-all`, `stats prune`, `job create --send`, `job send`, and `mail attachment` overwrite act immediately | `cli/commands/accounts.py::run` checks `isatty()` and prompts; the other commands do not | Irreversible actions happen on a stray Enter. `account delete` piped or scripted still refuses without `--yes`, which is correct, but the inconsistency is not | Confirmation table in section 14, with counts, `--yes`, and `--no-input`. The TTY prompt is kept and made uniform | C |
| D36 | S3 | There is no way to browse or pick a file, a template, an account, or a batch. Every identifier must be known in advance and typed | all commands | Humans must copy ids between commands | Pickers for accounts, batches, jobs, mail, templates, and files, each with search. Typing an id still works | A |
| D37 | S3 | There is no first-run flow. A new install requires the user to know the order: config, service, vault, account, connect, send | no `init` | The empty state is a set of error messages, not a path | `downcroc init`, idempotent, state-aware, with skips for what already exists | A |
| D38 | S3 | Destructive and long-running commands give no progress, and `--wait` gives none at all | `account attempt --wait`, batch submit | The tool looks hung | Progress lines with elapsed time, state changes, and a final summary. No spinners in non-TTY mode | A |
| D39 | S3 | There is no way to send a single message without building a campaign file, even though the daemon supports `job create` | no guided send | Testing an account requires the full batch contract | Guided compose writes a real one-message draft campaign and uses the same validate, preview, submit path. `job create` stays for agents | B |
| D40 | S3 | `batch show` does not show follow-up steps or their ids, so `batch followup --step` is unusable | `cli/commands/batches.py::_show` | Follow-ups cannot be added without reading the source | Show `follow-ups` with key, `after_days`, `when`, and `require_approval`; add them to `--json` | B |

### 3.9 Failure of the current review loop

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D41 | S1 | `batch preview` requires a running daemon, a vault, and the token, so a syntax error in a campaign cannot be checked offline | `core/batches/service.py::preview` runs inside the daemon | The feedback loop is unavailable exactly when a new user is writing their first file | `batch validate` runs the same parser in the CLI process, with no daemon, no vault, and no network. `batch submit --dry-run` is the server-side twin | B |
| D42 | S2 | Preview errors show a field path but not the row or message key for every issue; warnings and ignored fields are not printed at all. The daemon already returns every issue in `details`, so the CLI is discarding all but the first | `PreviewOut`, `cli/client.py::_raise`, `cli/commands/batches.py::_preview`; `core/inputs/report.py::raise_if_any` | Fixing a 500-row CSV becomes a guessing game, and a file with six errors takes six round trips | Print every issue with row, key, field, and message. Print warnings and ignored headers before the table, not after it. Carry all issues in the error `details` (D2) | B |
| D43 | S2 | The API docs are disabled by design, so there is no browsable contract even for agents | `api/app.py` disables `/docs`, `/redoc`, `/openapi.json` | `downcroc openapi` exists but is not discoverable | Keep the endpoints disabled. Add `downcroc openapi -` to print, mention it in help, and generate the input schema separately | B |
| D52 | S1 | A batch cannot be directed at an account. `batch preview` and `batch submit` have no `--account`, a per-message `account` is accepted and silently ignored, and a top-level `account` or `routing` is rejected as unknown | `core/inputs/campaign_message.py` `IGNORED_HEADERS`; `core/inputs/campaign_policy.py` only accepts routing under `campaign`; `cli/parser.py` | A user cannot pin a sender, `preview` prints `account -` and exits 0, and the failure arrives at `submit` as `account_unavailable`. On an `auto` campaign the same batch silently goes out through whichever account wins | Add `--account` to `preview`, `submit`, `followup`, and `validate`, and make it set `campaign.routing` (`mode = "fixed"`). Stop ignoring a per-message `account`: reject it with `unknown_field` and a hint that names `campaign.routing.account`. Preview fails when routing resolves no connected account, and prints the routing decision and per-account counts. Section 9.2 is unchanged as the contract | B |

### 3.10 First-run vault

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D53 | S1 | A non-TTY `vault unlock` and `account connect` call `getpass` without an `isatty` check, so cron, CI, and containers get a `GetPassWarning`, a Python traceback, `termios.error`, and `EOFError` | `cli/commands/vault.py::_password`, `cli/commands/accounts.py::_password` | Automation sees interpreter internals and file paths instead of "no terminal, use `--password-stdin`" | Check `sys.stdin.isatty()` and `sys.stderr.isatty()` before prompting. On failure print `error: no_terminal: no terminal for a password prompt` with a hint naming `--password-stdin` and `--password-file`, and exit 1 | A |
| D54 | S1 | The first `vault unlock` silently creates the vault with one prompt and no confirmation. There is no `vault init`, and the log line `vault.created` never reaches the user | `core/vault_service.py` unlock path; `cli/commands/vault.py` | A typo becomes the permanent master password, and the user is not told they just created the only copy | Add `vault init` with a double prompt, a mismatch re-prompt, and a warning that the password cannot be recovered. `unlock` on a missing vault refuses and names `vault init`. `init` calls `vault init`. `--password-stdin` stays single-shot and is documented as such | A |
| D55 | S2 | The failure that crosses the lockout threshold is reported as an ordinary bad password. The next attempt is throttled, but the CLI drops the throttle hint (D2), so the only visible difference is a slower reply, and `vault status` can read `retry_after_s 0.0` once the wait has elapsed | `core/vault_service.py::_record_failure` sets `_next_attempt`; `VaultThrottled` carries a hint; `cli/client.py::_raise` discards it; `cli/commands/vault.py::_show` always prints both fields | A user cannot tell they are being throttled, and a script cannot tell either, so the next retry looks like a wrong password and invites more attempts | On the failure that crosses the threshold, return `vault_throttled` with `retry_after_s` instead of `vault_bad_password`, and keep it on subsequent attempts. Print the wait and the remaining attempts. `vault status` reports the pending delay and shows `attempts_left` and `retry_after_s` only when locked or throttled | C |
| D56 | S2 | Unlocking an already unlocked vault is an error | `api` returns `vault_already_unlocked`; `cli/commands/vault.py` passes it through | Every script must check state first, and a retry after a timeout fails even though the vault is where it should be | Make `unlock` idempotent: exit 0, print `state unlocked` and `changed no`. Keep a distinct error only when a different password is supplied while unlocked | C |
| D57 | S3 | `--password-stdin` reads one line and silently ignores the rest, so a pasted multi-line value appears to work while being truncated. There is no file or environment source | `cli/commands/vault.py::_password` uses `readline()`; `cli/commands/accounts.py::_password` | A secret with a trailing newline becomes a different secret, and systemd or container secret mounts need a shell pipeline | Reject extra non-empty lines with an `input_invalid` error naming the flag. Add `--password-file PATH` (mode checked, `0600`, no trailing-newline retention) beside `--password-stdin` | C |
| D75 | S3 | The master password must be typed at every unlock, so the product asks a person to remember a second password forever. There is no way to delegate it to the computer login, and the security plan explicitly rules that out | `cli/commands/vault.py` prompts on every unlock; `core/vault_file.py` derives only from a typed password; `plan/04-security.md` said no keyring integration | The vault password becomes the thing people write on a sticky note or reuse from their login, which is worse than either alternative | Offer the system credential store at `vault init` and `vault keyring enable`, read it silently on unlock, print the source, fall back to the prompt with one line when the store is unavailable, and never enable it under `--no-input` without `--keyring` (section 6.1 and Q-L) | A |

### 3.11 Daemon and service

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D58 | S1 | `service status` exits 0 for `stopped` and `stale` | `cli/commands/service.py::run` returns 0 unconditionally | A health check cannot detect a dead daemon, so monitoring reports healthy while nothing runs | Exit 1 for `stopped` and `stale`, keep 0 for `running`. Print the start hint on failure. `--json` carries `running: bool` and `state` | C |
| D59 | S2 | `service start` blocks for 15 seconds or more and prints one line only after it finishes | `runtime/service/lifecycle.py::start`; `cli/commands/service.py` | On a slow disk the user cannot tell whether it is working, and a timeout looks like a crash | Print `starting ...` before the wait, poll health with an elapsed counter, and on timeout print the unit path, the last state, and `downcroc logs`. Add `--timeout` | A |
| D60 | S2 | The CLI HTTP client has no timeout, so a slow or wedged daemon request blocks forever. A tester reported three `batch preview` calls hitting a 20 s external timeout; not reproduced, so the cause is unconfirmed | `cli/client.py` builds an `httpx` client with default timeouts | One slow request makes the tool look hung, and the reported preview hang cannot be ruled out | Set explicit connect and read timeouts, expose `--timeout`, and map expiry to `daemon_timeout` with the command, the elapsed time, and the daemon-down hint. Test with a fake server that accepts and never answers | C |

### 3.12 Filters and limits

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D61 | S2 | Invalid filters are silently accepted and return empty or zero: `job list --state nonsense`, `mail list --since nonsense`, `mail list --folder NOPE`, `stats summary --account acct_missing` all exit 0 | `cli/parser.py` has no `choices`; `cli/commands/*` pass values through; `api` returns an empty array or an empty stats row | A typo is indistinguishable from "no data", which hides real breakage and invites bad decisions | Validate enums, dates, and ids client-side with `argparse` `choices` and the shared date parser. Return `account_not_found` and `folder_not_found` for identifiers instead of empty results. Exit 1 and name the accepted values | C |
| D62 | S2 | `logs --limit 0` and `--limit -1` are accepted as "no limit" and dump the entire log. `--since nonsense` prints `cannot read --since nonsense` with no `error:` prefix and no format hint | `cli/commands/logs.py` | A mistyped limit produces thousands of lines; a mistyped date gives advice-free output | Reject `limit < 1` and `limit > max` with `usage` exit 2, use the shared date parser, and render both through the one error shape | C |
| D63 | S1 | `job create` accepts a `pending` account with no credential and queues a job that cannot send. The same account is refused by `batch submit` | `cli/commands/jobs.py`; `api` job create route does not check account state | The job sits queued and fails later with no warning at creation | Refuse unless the account is `ok` and has a credential, naming `downcroc account connect <id>`. `--force` queues with a printed warning. Apply the same preflight to `job send` | C |
| D64 | S2 | A missing `--text-file` leaks a raw Python errno: `error: [Errno 2] No such file or directory` | `cli/commands/jobs.py` reads the file directly | The only error in the product that does not use the error vocabulary, and it exposes a path and a Python exception | Route every local read through `cli/paths.py` and return `input_unreadable` with the field, the path, and a hint. Extends D26 | C |

### 3.13 Output leftovers

| ID | Severity | Defect | Evidence | Impact | Fix | Phase |
|---|---|---|---|---|---|---|
| D65 | S2 | `vault unlock` prints an unlabeled `account / credential` table, and `account list` repeats the account id column. The header `account` reads as a field name and the table has no heading | `cli/commands/vault.py::_show` prints `data["accounts"]`; `cli/commands/accounts.py::_list` | The most security-sensitive command ends with unexplained output about credentials | Remove the table from `vault` entirely: the vault reports its own state. Credentials are reported once, in `account show`, as `signed in: yes/no` (D32). `account list` shows one `signed in` column | C |
| D66 | S2 | `watcher_enabled` is true on a `pending` account, before any credential exists | account create defaults; `domain/accounts.py` | `account watch --on` appears to succeed on an account that cannot sync, and the list misreports intent as state | Default the watcher off until the account is connected. `watch --on` on a `pending` account prints a warning and leaves the flag off. Display `watch` as `off (not signed in)` | C |
| D67 | S2 | `account show` renders two unaligned blocks with no section labels, so `sync`, `quota`, and `routing` values run together | `cli/commands/accounts.py::_show` | Reading an account, the screen most used for diagnosis, requires guessing which field belongs to which group | Render labelled sections (`identity`, `sync`, `quota`, `routing`) with one shared key width, and mark every derived value read-only (D31) | C |
| D68 | S2 | `backup` before the first boot prints `backup failed: database does not exist` with no `error:` prefix and no hint. `restore` logs `backup.verify_failed` twice and only the basename, so the log cannot identify the file | `cli/commands/backup.py`; `core/backup/*` verify path | First-run backup fails without saying that the daemon has never run, and a failed restore is hard to trace | Render both through the one error shape. Name the missing database, the data path, and `downcroc service start`. Log the absolute path once, at `warning`, and deduplicate the event | C |
| D69 | S2 | `argparse` failures print a usage block and exit 2, while every domain error is `error: code: message` and exits 1 | `cli/parser.py` default `error()` | A script needs two parsers, and a human gets two visual languages | Override `ArgumentParser.error` to print one `error: usage: ...` line plus the relevant `-h` hint, exit 2. With `--json`, emit the error object on stderr | C |
| D70 | S3 | Successful mutations print the result and no next step: `created acct_... (pending)` stops there | every create command | A first-time user has to know the next command, which is the problem `init` exists to solve | Every mutating command prints `next: <command>` when interactive, suppressed by `--quiet` and replaced by a JSON field under `--json`. `account add` names `account connect`, `batch submit` names `batch show`, `provider add` names `account add` | A |
| D71 | S3 | `openapi -o` silently creates missing parent directories | `cli/commands/openapi.py` | A path typo succeeds and writes somewhere unexpected | Require an existing parent, or add `--mkdir` to create it deliberately. Print the absolute path written | C |
| D72 | S3 | `account watch ID` requires `--on` or `--off` even on a TTY | `cli/parser.py`; `cli/commands/accounts.py` | A one-word toggle takes a flag lookup | On a TTY with no flag, show the current state and ask `watch? [y/N]`. Flags unchanged | A |

### 3.14 Issues deliberately not fixed in 09

| ID | Issue | Why deferred |
|---|---|---|
| D44 | Account quota and policy editing | Requires new API routes and a decision about whether limits are per-account or global |
| D45 | Message body encryption at rest | Threat model decision, not a CLI defect |
| D46 | Gmail OAuth client publication | External process, tracked separately in the decision log |
| D47 | Interactive shell as a persistent REPL | Menus cover the flows; a REPL adds a state machine with no proven need |
| D73 | Shell completion (`completion bash|zsh|fish`) | Useful but not needed to complete a first send. The help topics and `-h` cover discovery in release 1. Release 2 |
| D74 | `vault passwd` (rekey the master password) | Needs a re-encrypt path in the vault service and an API route. The double prompt in `vault init` removes the typo case that made it urgent. Release 2 |

### 3.15 Independent tester cross-check

`.scratch/downcroc-cli-ux-report.md` is a black-box report against `1.0.0rc1`. It is folded in
above. This table maps its identifiers to the register so nothing is lost and nothing is fixed
twice.

| Tester | Register | Note |
|---|---|---|
| B1 | D50, D51, D29, D49 | Confirmed. The report's workaround, `provider add`, is adopted |
| B2 | D50 | Confirmed, same defect as B1 |
| B3 | D52 | Confirmed with a correction: the contract already accepts `campaign.routing.account`, and only a per-message `account` is ignored. The design keeps routing, so the fix is a flag, a hard error, and a failing preview, not a new per-message field |
| B4 | D35, D54, D37, D3 | Mostly confirmed. The claim that `account delete` never prompts on a TTY is wrong: `accounts.py` checks `isatty()` and prompts. The tester's harness piped stdin, which correctly refuses. The wording in D35 is corrected |
| H1 | D53 | Confirmed |
| H2 | D54 | Confirmed |
| H3 | D55 | Confirmed |
| H4 | D56 | Confirmed |
| H5 | D58 | Confirmed |
| H6 | D17, D42, D2 | Confirmed. Correction: `Issues.raise_if_any` already carries every issue; the CLI drops all but the first, which is D2. The allowed-field list is D17 |
| H7 | D28, D18, D16 | Confirmed. `--template` gains a path form and the template commands list names |
| H8 | D60 | Unreproduced by the tester and not reproduced here. A client timeout is added so a hang cannot recur, but no hang is claimed as fixed |
| H9 | D63 | Confirmed |
| H10 | D61 | Confirmed |
| H11 | D62 | Confirmed |
| H12 | D64 | Confirmed |
| H13 | D65, D32 | Confirmed |
| M1 | D66 | Confirmed |
| M2 | D67 | Confirmed |
| M3 | D11 | Duplicate of D11 |
| M4 | D1, D2 | Covered by the auth-kind branch and hint passthrough |
| M5 | D1 | Covered |
| M6 | D57 | Confirmed |
| M7 | D68 | Confirmed |
| M8 | D68 | Confirmed |
| M9 | D22 | Duplicate of D22 |
| M10 | D20, D16, D18, D73 | `doctor`, `batch example`, and examples are in 09; completion is deferred |
| M11 | D9 | Duplicate of D9 |
| M12 | D55 | Covered |
| M13 | D13 | Extended: `logs` with no daemon also prints the daemon-down hint |
| M14 | D59 | Confirmed |
| M15 | D14, D61 | Covered |
| M16 | D69 | Confirmed |
| M17 | D12 | Duplicate of D12 |
| L1 | D70 | Confirmed |
| L2 | D72 | Confirmed |
| L3 | D18, D33 | `--key` gets help text on `submit` as well as `preview` |
| L4 | D62 | Covered |
| L5 | D61 | Duplicate of H10 |
| L6 | D61 | Duplicate of H10 |
| L7 | D71 | Confirmed, with the caveat that the tester ran as root |
| L8 | D57 | Covered by `--password-file` |

---

## 4. Mode detection

The single predicate every prompt consults:

```
interactive = (
    stdin.isatty()
    and stdout.isatty()
    and not args.json
    and not args.no_input
    and not os.environ.get("CI")
)
```

Rules:

- `--json` always implies non-interactive. JSON on stdout must be the only stdout content.
- `--no-input` means "fail rather than ask". It does not mean "assume yes".
- `--yes` supplies consent for a named destructive action, but does not enable prompts.
- Piped stdin disables prompts. `vault unlock --password-stdin`, `account connect --password-stdin`,
  and `--text-file` remain the ways to supply input without a TTY.
- `DOWNCROC_NO_INPUT=1` is honoured as an escape hatch for wrappers.
- A command that needs a value and cannot prompt fails with a message naming the flag, for
  example: `provider is required; use --provider gmail, or run interactively`.

Mode matrix:

| Situation | Behaviour |
|---|---|
| TTY, no flags | Menu or prompt, then the same handler |
| TTY, `--json` | No prompt, JSON only |
| TTY, `--no-input`, missing value | Error naming the flag, exit 1 |
| Piped stdout | No prompt, plain or JSON output |
| Piped stdin | No prompt, error on missing required input |
| `CI=1` | Same as piped stdin and stdout |
| `TERM=dumb` | No colour, no glyphs, prompts still allowed if a TTY |
| Windows without a console | No prompt |

`argv` never carries a secret. The only concession is `--password-stdin`, which is already the
documented script path.

---

## 5. Command surface

### 5.1 Existing surface

```
downcroc
  serve
  service {start,stop,status,install,uninstall} [--print] [--json]
  openapi [-o FILE]
  backup [PATH] [--include-logs]
  restore PATH
  auth status [--json]
  vault {status,unlock,lock} [--password-stdin] [--json]
  account {list,show,add,delete,providers,attempt,connect,verify,sync,watch}
  batch {list,show,preview,submit,approve,cancel,followup,suppression}
  job {list,show,send,create}
  failed {list,show,retry,retry-all}
  config {show,schema,set}
  stats {summary,hourly,daily,batches,accounts,rebuild,prune}
  mail {list,show,threads,thread,attachment}
  logs [...]
```

Gaps: no `init`, no `send`, no `review`, no `status`, no `doctor`, no `template`, no input
discovery, no `provider`, no `vault init`, no `vault keyring`, no `service restart`, no `help`
command, no `docs`, no `update` (ticket 07), no `completion` (deferred, D73).

### 5.2 Target surface

New or changed items marked with `+`.

```
downcroc                              + state-aware: menu on TTY, state summary otherwise
downcroc init                         + first-run flow, idempotent
downcroc status                       + one-screen health and attention list
downcroc doctor                       + checks with fixes, exit 1 when unhealthy
downcroc send                         + guided send (file, CSV, or compose)
downcroc review                       + pending batches and approvals
downcroc docs [--open]                + print paths to the installed book
downcroc help [TOPIC]                 + same as -h TOPIC
downcroc -h [TOPIC]                   + command help or topic help
downcroc serve
downcroc service {start,stop,restart,status,install,uninstall}   + restart
downcroc openapi [-o FILE|-]          + `-` prints to stdout
downcroc backup [PATH] [--include-logs] [--json]        +
downcroc restore PATH [--dry-run] [--yes] [--json]      +
downcroc auth status [--json]
downcroc vault {init,status,unlock,lock}                + init
downcroc vault init [--password-stdin|--password-file PATH] [--keyring|--no-keyring]
                                      + double prompt, no overwrite, optional credential store
downcroc vault unlock [--password-stdin|--password-file PATH] [--keyring|--no-keyring]
                                      + idempotent, silent credential-store unlock
downcroc vault lock [--forget]        + --forget removes the stored password
downcroc vault keyring {status,enable,disable}          + OS credential store
downcroc provider list                + declarations and readiness
downcroc provider show ID             + hosts, ports, TLS, auth, notes, file path
downcroc provider add ID              + write a declaration, never a secret
downcroc provider edit ID             + open the file in $EDITOR, re-validate on save
downcroc provider remove ID           + refuses while accounts use it
downcroc account ...
downcroc account add --provider P --address A [--imap-host ...] [--smtp-host ...]
                                      + host and OAuth flags (D51)
downcroc batch schema [--json]        + full input contract
downcroc batch example [--kind K] [--write DIR]         + runnable starter files
downcroc batch validate PATH [--template T|PATH] [--account ID] [--json]  + offline validation
downcroc batch preview PATH [--account ID] [--all] ...  + routing target and truth
downcroc batch submit PATH [--dry-run] [--account ID] ...  +
downcroc batch show ID [--all] [--full]                 + follow-up steps and routing
downcroc template list                + templates in the config dir
downcroc template new NAME            + working template skeleton
downcroc template show NAME           + manifest, body, variables, rendered sample
downcroc template validate NAME|PATH  + parse and render check, offline
downcroc job ...
downcroc failed ...
downcroc config ...
downcroc stats ...
downcroc mail ...
downcroc logs ...
```

Global flags added everywhere: `--no-input`, `--yes` (only commands that need consent), `--wide`,
`--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout S`.

`--timeout` applies to every daemon request and defaults to a configured value (section 17). It is
the flag that turns a wedged daemon into `daemon_timeout` instead of a hung terminal (D60).

`--password-file PATH` is accepted wherever `--password-stdin` is, and is the recommended form
for systemd and container secret mounts (D57).

`--json` becomes universal, including `backup`, `restore`, `account delete`, `mail attachment`,
`init`, `send`, `review`, `status`, `doctor`, `template`, `batch schema|example|validate`.

`--version` stays.

### 5.3 Mapping of old to new

| Old | New |
|---|---|
| `batch preview` | unchanged, plus `--account`, truthful totals, and a hint to `batch validate` |
| `batch submit` | unchanged flags, plus `--dry-run`, `--account`, and help for `--key` |
| `batch approve --mode one|all` | unchanged, help rewritten to say what each does |
| `job create` | unchanged, plus account preflight and a warning when it targets a batch that does not exist |
| `account connect` | unchanged, but auth-kind aware |
| `account add` | unchanged flags, plus host and OAuth flags |
| `vault unlock` | unchanged, plus `--password-file`, the credential store, and idempotent success |
| `service status` | unchanged, but exits 1 when stopped or stale |
| bare `downcroc` | state-aware |

No command is removed. No flag is renamed in release 1. Two meanings are corrected in help
and prompts only (D7, D8), and `job create --batch manual` gains validation (D6).

`vault init` is new, so a script that relied on the first `unlock` creating the vault must now
call `vault init` first. Section 21 records this as an intentional break with a one-line upgrade
note.

---

## 6. Human flows

Every flow is a sequence of prompts. Each prompt has a default, an escape (`Esc` or `q`), and a
non-interactive equivalent. No flow can reach an action the flags cannot reach.

### 6.1 `downcroc init`

Purpose: from an empty home directory to a working daemon with one connected account.

```
$ downcroc init
downcroc 1.0
  config   ~/.config/downcroc
  data     ~/.local/share/downcroc
  state    ~/.local/state/downcroc

This directory becomes the only place downcroc stores anything.
Continue? [Y/n]

Start the daemon
  ( ) Run it now and leave it running after logout
  ( ) Install it as a login service (recommended)
  ( ) Do nothing, I will start it myself

[starts or installs]
daemon       running, pid 4213, http://127.0.0.1:8765
vault        not created

Create the vault password
  This password protects every mail credential. It cannot be recovered.
  Password: ********
  Again:    ********

Use my computer login for this password?
  ( ) Yes, keep it in the system credential store (recommended)
      you will not type it again, only your computer login
  ( ) No, ask me each time the daemon starts
vault        created, unlocked, keyring on (secret service)

The step is `vault init`. A mismatch re-prompts instead of creating. `init` never overwrites an
existing vault; it reports `vault exists, locked` and offers `vault unlock`.

The keyring question appears only when a usable store exists. On a headless machine it is
skipped with one line, `keyring unavailable, type the password instead`.

Add the first account
  Provider: ( ) Gmail  ( ) Microsoft 365  ( ) Other IMAP  ( ) Skip
  Address:  you@example.com
  Label:    you
account      pending

[auth method, asked whenever a provider has more than one door, no default]
  How should downcroc sign in to you@example.com?
  ( ) App password    about 2 minutes, no browser
                      needs 2-Step Verification on the mail account
  ( ) OAuth client    about 10 minutes in the provider console, once
                      survives a password change, not affected if the provider
                      stops allowing app passwords
  ( ) Back

[app-password branch]
  Gmail app passwords are 16 letters, generated at
  https://myaccount.google.com/apppasswords. 2-Step Verification must be on.
  App password: ********
  checking imap.gmail.com:993 ... 1.2s
  [ok] connected    imap.gmail.com, sent folder [Gmail]/Sent Mail
  SMTP is not checked here. The test message at the end proves it.
account      connected

[OAuth branch]
  This needs an OAuth client of type Desktop from the Google Cloud console.
  client id:     ....apps.googleusercontent.com
  client secret: ********
  written  ~/.config/downcroc/providers.toml  [providers.gmail]  mode 0600

  opening the browser to approve downcroc ...
  waiting for approval ... 12s
  [ok] connected    imap.gmail.com, sent folder [Gmail]/Sent Mail
  note     an unpublished client gets a seven-day refresh token. If the account
           stops working after a week, run this step again.
account      connected

[Microsoft 365 branch]
  Microsoft needs an app registration with a client id and a tenant id.
  client id:     ...
  tenant:        ...
  run this step again after the registration exists.
  ( ) Open providers.toml   ( ) Skip this account   ( ) Delete this account

[Other IMAP branch]
  This writes a provider declaration for your mail host.
  IMAP host:     imap.example.com
  IMAP port:     993
  IMAP security: ( ) SSL  ( ) STARTTLS
  SMTP host:     smtp.example.com
  SMTP port:     587
  SMTP security: ( ) STARTTLS  ( ) SSL
  Username:      you@example.com
  written  ~/.config/downcroc/providers.toml  [providers.fastmail]  mode 0600
  no password is written to this file

  Password: ********
  checking imap.example.com:993 ... 0.8s
  [ok] connected    imap.example.com, sent folder Sent
account      connected

[connect failed, any branch]
  [fail] not signed in to imap.gmail.com
         AUTHENTICATIONFAILED: invalid credentials
    hint: app passwords are 16 letters with no spaces and need 2-Step
          Verification. generate one at https://myaccount.google.com/apppasswords
  the password was not saved

  ( ) Try again   ( ) Change sign-in method   ( ) Edit provider   ( ) Exit

[after three failures]
  [fail] 3 attempts failed, stopping so the mailbox does not lock the account
  ( ) Change sign-in method   ( ) Edit provider   ( ) Exit

Send a test message? [y/N]
  To:      you@example.com
  Subject: downcroc test
  [sends through the normal job path]
done        1 account connected, daemon running
next        downcroc status
```

Rules:

- Idempotent. Each step checks current state and skips with a line saying why.
- If the daemon is already running, do not start a second one.
- If the vault exists, do not ask for a new password. Offer unlock instead.
- If an account exists, do not add one unless asked.
- The sign-in method is asked with no default and no preselection. Both doors carry a cost the
  project cannot remove, so the prompt states both costs and picks neither. Section 15 has the
  Gmail specifics.
- The account row is created before the credential is checked. A failed check leaves a
  `pending` account, so the address and label are not lost and the step can be resumed with
  `downcroc account`.
- A failed check stores nothing: no vault entry, no password in `providers.toml`, no echo, no
  log line. The password is written to the vault only after IMAP login succeeds.
- A successful check names what was checked, the IMAP host and the sent folder. It never claims
  SMTP. The test message at the end is what proves sending.
- Three failed attempts stop the flow with an explanation about mailbox lockouts, rather than
  prompting again.
- Service registration failure is reported and does not abort `init`; the daemon can still run
  detached.
- `init --json` performs no prompts and reports the state it found, with `--service`,
  `--no-service`, `--account-provider`, `--account-address` as the script path.

#### Vault password sources

Order of resolution for `vault init` and `vault unlock`:

1. `--password-stdin` or `--password-file`, which always win and never touch the store.
2. the system credential store, when an item exists and `--no-keyring` was not passed.
3. a prompt, when a terminal is available.

`--keyring` requires the store and fails with `keyring_unavailable` when there is none, which is
the form a script should use. `--no-keyring` skips the store and prompts.

What is stored is the master password itself, under service `downcroc` and account
`<absolute vault path>`. The derived key is never stored, the daemon never reads the store, and
no mailbox credential is ever written there.

The login password is not read or verified, because neither Linux nor Windows exposes a portable
way to check it, and a later login password change must never lock the vault. What the store
removes is the second password from memory: after `init`, the person types the computer login and
nothing else. Typing the same string at init is allowed and common, but it is not required.

Once enabled, an interactive command that needs credentials and meets a locked vault unlocks
silently and prints one line:

```
vault      unlocked (system credential store)
```

It does not do this off a TTY. `downcroc vault unlock --keyring` is the scriptable form, and it
is the only way automation gets the same behaviour.

A store that is missing or locked changes nothing except one line:

```
keyring    unavailable, type the password instead
Password: ********
```

A stored password that no longer works is deleted, the prompt appears, and a successful unlock
offers to store the new one. Nothing is overwritten silently.

```
downcroc vault keyring disable     deletes the item, the vault password is unchanged
downcroc vault lock --forget       deletes the item and locks now
downcroc vault keyring status      on (secret service), off, or unavailable
```

The trade, stated in the prompt and in `topic vault`: while the store is on, anything running as
you in your logged-in session can unlock the vault. The vault protects the files at rest, not a
compromised session, and the enabled state is shown by `status` and `doctor` so it is never a
surprise.

### 6.2 Bare `downcroc`

On a TTY, state-aware:

| State | Screen |
|---|---|
| No config | "No installation found at <paths>. Run `downcroc init`." with a `Run init now?` prompt |
| Daemon stopped | state summary plus `Start the daemon now?` |
| Running, vault locked | state plus `Unlock now?`; with the credential store on it unlocks without a prompt |
| Running, unlocked, no accounts | state plus `Add an account now?` |
| Running, accounts exist | home menu |

Off a TTY: print the state summary and the single next command, then exit 0 if healthy, 1 if
not. Never print "start it with" when it is already running.

The bare command is never a dead end. After `Start the daemon now?` it continues to `Unlock` or
`Create the vault` and then to `Add an account`, so a person who typed three words reaches the
same state as `init`. When the daemon is healthy and an account exists, it prints the home menu.
Off a TTY it prints the state, the next command, and a one-line `downcroc -h` pointer, so a
person who expected help still finds it (D12, D37, M17).

Home menu:

```
downcroc                                          daemon running 2h14m  unlocked
  8 accounts, 1 needs attention      1,204 queued      37 sent this hour      3 failed

  > Send a campaign
    Review pending batches
    Status
    Accounts
    Mail
    Failures
    Settings
    Back up or restore
    Help
    Quit

  up/down move   enter select   / filter   ? help   q quit
```

Every row shows live counts where a count exists. Selecting a row opens the feature menu, not a
command line.

### 6.3 Accounts

Entry: `downcroc account` (new: no action runs the menu), `downcroc account list`, or the home
menu.

Account list:

```
  address                 provider   signed in   watch   allowance        state
  ana@example.com         gmail      yes         on      62/200 today     ok
  bo@example.com          microsoft  no          off     -                needs re-auth
  cy@example.com          generic    yes         off     18/80 today      paused
```

Selecting an account opens an action menu relevant to its state:

- `ok`: verify, sync now, watch on/off, show details, delete.
- `needs_reauth`: reconnect using the account's own door (OAuth attempt with URL and wait, or a
  fresh app password), show details, delete.
- `pending`: connect (auth-kind aware), show details, delete.
- `paused`: resume (where supported), show details, delete.

`account add`:

1. Pick provider from a list with label and the doors it offers.
2. Type the address, validated locally before the request.
3. Type a label, defaulting to the local part.
4. Pick a sign-in method. No door is preselected.
5. Create. Then, in the same flow, connect using the chosen method.
6. The connect step ends as `connected`, `not signed in` with the reason and the fix, or
   `cancelled`. Only `connected` stores the credential.
7. On success, offer `sync now` and `watch on`, then a test message.
   The connect check covers IMAP login only. SMTP is proven by the test message, and the flow
   says so rather than claiming a send check that did not happen.

| Provider | Doors | Default |
|---|---|---|
| Gmail | app password, OAuth client | none |
| Microsoft 365 | OAuth client | none |
| Other IMAP | app password | none |

Each door line states three things: what the user has to do outside downcroc, how long that
takes, and what the door does not protect against. Gmail's two doors are described in
section 15.

Selecting a door that is not configured yet explains the exact file, section, and key, offers
to open it in `$EDITOR`, and leaves the account `pending` so the attempt can be resumed. It
never offers a door that cannot work for that provider.

`account attempt` prints the URL, says what to do, waits with a progress line, and prints the
result. `--wait` is unchanged; the interactive flow always waits.

#### Connect result

Every connect attempt ends in exactly one of three shapes:

```
checking imap.gmail.com:993 ... 1.2s
[ok] connected    imap.gmail.com, sent folder [Gmail]/Sent Mail
[fail] not signed in to imap.gmail.com
       AUTHENTICATIONFAILED: invalid credentials
```

Rules:

- The tick is green and the cross is red when colour is on. The words `connected` and
  `not signed in` are always printed, so the line survives `NO_COLOR`, `TERM=dumb`, and a
  terminal without a Nerd Font.
- The provider's response text is printed verbatim. It is the only thing a support request
  needs, and rewording it into "authentication failed" destroys the diagnosis.
- The hint names the fix, not the symptom: 2-Step Verification and a fresh app password, a
  client id and secret pair, or a host and port mismatch.
- Nothing is stored on failure, and the password is never echoed, logged, or written to a file.
- The account row already exists and stays `pending`, so `downcroc account` can resume it.
- Three failures stop the flow and offer `Change sign-in method`, `Edit provider`, `Exit`,
  because a fourth attempt only risks locking the mailbox.
- Non-interactive modes print the same three shapes without the menu and exit 1 on failure.

#### Providers

`downcroc provider` (new) is the surface that makes B1 fixable without hand-editing TOML.

```
Providers
  > Gmail            OAuth client  not configured   set oauth_client_id and oauth_client_secret
    Gmail            app password  ready
    Microsoft 365    OAuth client  not configured   set oauth_client_id and oauth_tenant
    Other IMAP       app password  not configured   set imap_host and smtp_host

  > Add  Show  Edit  Remove  Back
```

- `list` is the same table as `account providers`, with the absolute declaration path in the
  footer: `declarations: ~/.config/downcroc/providers.toml and ~/.config/downcroc/providers.d/`.
- `show ID` prints every field, the merged source file, the auth kind, the door, readiness, and
  the `notes` line.
- `add ID` asks for the fields that provider needs, writes `[providers.<id>]` through the same
  registry merge path as a hand-written file, mode `0600`, and prints the path and key names.
  It refuses to overwrite an existing declaration.
- `edit ID` opens the merged source file in `$EDITOR`, re-validates on save, and reports the
  field that failed without discarding the file.
- `remove ID` refuses while any account uses it, and prints the accounts.
- No provider or account command accepts a secret on the command line. The OAuth client secret is
  accepted through a masked prompt or `--password-file` and written to `providers.toml` mode
  `0600`, because the daemon needs it at token exchange. Mailbox app passwords go to the vault
  and never to `providers.toml`.
- Every provider error elsewhere in the CLI names the file, section, and key, and points at
  `downcroc provider show <id>` (D50).

Agent path: unchanged flags, plus `--json` everywhere and hints preserved.

### 6.4 Send

Entry: `downcroc send`, or home menu. Three source kinds.

```
Send
  > A campaign file (JSON)
    A CSV plus a template
    One message, composed here

File: ~/campaigns/march.json        [tab completes, ~ expands]
```

For any source, the flow continues:

1. Resolve the path to absolute, client-side.
2. Validate offline. Show errors with row, key, and field. Offer to open the file in `$EDITOR`
   and validate again. Never proceed with errors.
3. Preview: total messages, sample of up to 5, warnings, ignored headers, routing assignment
   counts, follow-up steps, attachments, duplicates.
4. Choose an account or `Auto`:
   - `Auto` (default) routes by the campaign's `routing` policy.
   - `One account` pins every message: `routing.mode = "fixed"`, `routing.account = "<id>"`,
     and the CLI passes `--account <id>`.
   For a CSV or a composed message the picker is the same.
5. Choose approval, in words:
   - `Hold everything for review` (campaign `review`), default.
   - `Send as soon as it is due` (campaign `auto`), with a warning that this sends without a
     second look.
6. Confirm: `Submit 1,240 messages from 3 accounts, held for review? [y/N]`.
7. Submit. Print the batch id, counts, and the next command or menu (`review` if held).

CSV branch:

1. Pick a template from `<config>/templates`. If none, offer `template new`.
2. Show the required CSV headers (`email` plus the variables used by the template).
3. Pick the CSV, validate, preview one rendered row.

Compose branch:

1. Pick sending account (only connected accounts).
2. To, name, subject.
3. Body opens `$EDITOR` with a template header comment. Text is the source of truth; optional
   HTML is a separate file.
4. Optional attachments, picked one at a time, copied into the draft directory.
5. The flow writes `~/.local/share/downcroc/drafts/<date>-<slug>/campaign.json` plus assets.
6. It then runs validate, preview, confirm, submit. The draft path is printed and reusable.

The draft is the record. It can be edited, re-validated, re-submitted, or handed to an agent.
`job create` remains for one-off sends from scripts but is no longer the human path.

Agent path:

```
downcroc batch validate campaign.json
downcroc batch submit campaign.json --approve none --json
downcroc batch submit campaign.json --approve all --json
downcroc batch submit campaign.json --account acct_... --approve none --json
```

When `--account` is passed, the CLI sets `campaign.routing` to `fixed` for that account and
prints the resolved routing line. A per-message `account` field is rejected, not ignored, and the
error names `campaign.routing.account` (D52).

### 6.5 Review

Entry: `downcroc review`, home menu, or `batch list --state awaiting_approval`.

```
Pending review
  batch                     messages   sent   failed   created
  b_01H...  march outreach   1,240        5      0       12m ago
  b_01H...  follow-up day 3     84        0      0       2h ago

  > Open 1,240-message batch
    Approve all and send
    Send one sample now
    Cancel the batch
    Back
```

Opening a batch shows counts, sample recipients with rendered subject and first lines, the
approval mode, routing, follow-ups, and any warnings. Actions are spelled out:

- `Send one sample now` sends exactly one job and leaves the rest held. This is what
  `--approve one` means, and the prompt says so.
- `Approve the remaining 1,239 and send` is the `all` path.
- `Cancel` shows how many jobs will be cancelled and requires confirmation.

For a campaign submitted with `approval = auto`, the batch is already sending. The menu shows
`sending`, offers `cancel`, and does not offer approval.

Agent path: `batch show ID --json`, `batch approve ID --mode one|all`, `batch cancel ID --yes`.

### 6.6 Status and doctor

`downcroc status` is one screen, always the same shape:

```
daemon     running, pid 4213, 2h14m, http://127.0.0.1:8765
vault      unlocked, keyring on (secret service)
api token  accepted
accounts   8 total, 1 needs re-auth, 1 pending
queue      1,204 queued, 37 sent this hour, 3 failed
inbound    41 today, 37 replies
service    installed (systemd user), active
log        ~/.local/state/downcroc/logs/downcroc.jsonl, last write 4s ago
```

Every line is a check with a state. A bad state prints the next command on the same line:
`accounts 1 needs re-auth, run: downcroc account`.

`downcroc doctor` runs the checks and prints pass/fail with fixes:

| Check | Failure message and fix |
|---|---|
| config parses | field and value, `downcroc config show` |
| paths writable | path, required mode |
| database revision | expected versus found, `downcroc service start` runs migrations |
| daemon alive | pid and port, `downcroc service start` |
| health reachable | URL and error, `downcroc logs --since 5m` |
| token accepted | `downcroc auth status`, restart guidance |
| vault state | locked is not a failure; corrupt is |
| credential store | `vault keyring status` and the backend name; `unavailable` is information, not a failure |
| service definition | installed, path, manager state |
| provider readiness | per door: missing client id or secret, missing tenant, empty hosts, notes |
| log writable | path and error |
| port free or owned | port and pid |
| clock skew | offset if detectable |

Exit 1 if any check fails, 0 otherwise. `--json` emits every check with `ok`, `detail`, `fix`.

### 6.7 Mail

Entry: `downcroc mail`, home menu.

```
Mail
  > Inbox (41 today, 37 replies)
    Threads
    Search
    Back

Inbox filter: [all] [replies] [bounces] [no reply] [account] [date]
```

List rows show date, from, subject, reply state as a word, attachment count, id. Selecting a
row opens the message: headers, full body, attachments, thread, and the job that caused it.
`Save attachment` asks where, refuses to overwrite without confirmation, and prints the final
path.

Reply states are shown as words with a short explanation on first use:

| Stored | Display | Meaning |
|---|---|---|
| `confirmed` | confirmed reply | headers prove it answers a job |
| `probable` | likely reply | subject and participant match, headers do not |
| `late` | late reply | arrived after the reply window |
| `bounced` | bounce | a delivery failure, not a person |

### 6.8 Failures

```
Failures
  3 jobs failed
  > job_01H...  ana@example.com  550 mailbox unavailable   permanent   2 attempts
    job_01H...  bo@example.com   421 try later            retryable   1 attempt

  > Show  Retry  Retry all  Back
```

Retry all shows the count and the affected accounts before asking.

### 6.9 Settings

```
Settings
  > Sending limits
    Reply window
    Log level
    Appearance
    Back
```

`config show` is a table of dotted keys with values and sources (default, file, environment).
`config set` validates before writing and prints the old and new value. Editing a setting that
needs a restart says so. Appearance covers glyphs, colour, and width.

### 6.10 Backup and restore

`backup` without a path proposes a directory under the data directory, prints the resolved
target before writing, and prints the final size and path.

Before the first boot there is no database. `backup` then prints:

```
error: no_database: the database does not exist yet
  path: /home/you/.local/share/downcroc/downcroc.db
  hint: start the daemon once with `downcroc service start`, then back up
```

`restore` is a two-step flow:

1. Read the bundle and print the manifest: created at, downcroc version, schema revision,
   accounts, batches, jobs, messages, threads, attachments, included logs, total size.
2. State: "This replaces the current data at <path>. The current data is moved to
   <backup path>." Require `restore` typed at the prompt, or `--yes`.
3. Stop the daemon if running, restore, restart if it was running, and print the result.

`restore --dry-run` stops after the manifest. `restore` refuses while the daemon is running
unless `--stop` is given, and says how to stop it.

A verify failure logs one `backup.verify_failed` warning with the absolute path, then one
`restore.refused` event with the reason. The path is never reduced to a basename (D68).

### 6.11 Templates

```
Templates in ~/.config/downcroc/templates
  > intro        subject: Hello {{name}}        3 variables
    followup     subject: Following up           2 variables

  > New  Show  Validate  Edit  Back
```

A template argument is a name under `<config>/templates` or a path to a directory that holds
`template.toml`. The two are told apart by the presence of a path separator, `~`, or an existing
directory. A path is resolved client-side and read directly, so a template kept beside the
campaign works (D28).

`template new NAME` writes:

```
<config>/templates/<name>/
  template.toml
  body.txt
  assets/
```

with a working manifest and a body that uses at least one variable and one default, so it
validates immediately. `template show` prints the manifest, the variables used, and a rendered
sample with placeholder values. `template validate` parses and renders every declared variable
without a daemon.

### 6.12 Logs

`logs` with no matching file prints `no log file at <path>` and exits 1, and adds the
daemon-down hint when the service is also stopped. With a file, it prints events, and prints
`showing 200 of 1,834, use --since or --limit` when clipped. `--follow` streams and prints a
line when the daemon rotates the file.

`--limit` must be at least 1 and at most the configured maximum. `--since` accepts the formats
in `logs --help` and nothing else. A bad value is a usage error that names the accepted forms,
not a silent expansion and not a bare sentence without an `error:` prefix (D62).

---

## 7. Navigation model

- Menus are line-oriented. No alternate screen buffer. Scrollback survives, and piping a
  session still produces readable text.
- Keys: arrows and `j`/`k` move, `enter` selects, `/` filters, `?` contextual help, `esc` back,
  `q` quit from the top menu only.
- Every screen prints a breadcrumb: `downcroc > account > ana@example.com`.
- State is re-read after every action, so counts change instead of going stale.
- Ctrl-C cancels the current prompt and returns to the menu. Ctrl-C twice exits.
- Free text that is longer than a line (bodies, subjects with newlines) opens `$EDITOR`.
  `$VISUAL` wins if set. The editor is chosen from `$VISUAL`, `$EDITOR`, `nano`, `vi`, and the
  flow says which one it used.
- Secrets use masked prompts only. They are never echoed, never placed in a draft file, and
  never passed as an argument.
- No prompt has a destructive default. The default selection is always the safe action.
- Prompts are not a wizard that traps the user. Every step can be skipped, and every step says
  which flag does the same thing.
- Width is respected: menus work at 60 columns, wrap at the terminal width, and never truncate
  an identifier.

---

## 8. Help system

### 8.1 Behaviour

| Invocation | Result |
|---|---|
| `downcroc -h` | command list, one-line description each, global flags, and the topic list |
| `downcroc <command> -h` | argparse usage with help text on every flag, plus examples |
| `downcroc -h <topic>` | topic page (concepts, flows, formats) |
| `downcroc help` | same as `downcroc -h` |
| `downcroc help <topic>` | topic page |
| `downcroc -h ui` | interactive help: pick a topic, read it, stay in the browser |
| `?` inside a menu | the topic for the current screen |
| `downcroc <command> --help` | same as `-h` |

`-h` with an unknown topic prints the topic list and exits 2.

### 8.2 Topics

Static topic pages, packaged with the CLI, one file each:

```
start        install, first run, the daemon model
ui           how the interactive layer works, keys, when prompts are skipped
send         choosing a source, composing, previewing, approving
campaign     the JSON campaign format
csv          CSV plus templates
templates    template layout and variables
followups    follow-up steps and reply windows
batch        batch states and what each action does
accounts     providers, auth kinds, OAuth, app passwords
providers    declaration files, merge order, readiness, provider commands
vault        vault init, password rules, lockout, password sources
mail         reading, threads, reply states, attachments
jobs         job states, retries, failures
status       health, doctor, logs
backup       backup and restore
config       settings and sources
json         the JSON output and exit-code contract
glossary     every domain word
```

Each topic contains: what it is, the commands that use it, one worked example, the common
mistakes, and links to related topics. Topic text is the source for the docs book (ticket 04),
so the two cannot drift.

### 8.3 Command help

Every flag gets a `help=` string. Every command gets an `epilog` with two or three real
examples. Missing help text is a test failure:

- A test walks the parser tree and asserts that every argument has help text.
- A test asserts every leaf command has at least one example.

Example epilog:

```
examples:
  downcroc batch validate campaign.json
  downcroc batch validate rows.csv --template intro
  downcroc batch submit campaign.json --approve none
```

### 8.4 Errors teach

Every `CliError` carries an optional `hint`. The renderer prints:

```
error: batch_invalid: messages[3].to.email: not an email address
  hint: fix row 4, or run downcroc batch validate campaign.json
  field: messages[3].to.email
  detail: key=m4, row=4
```

When an error has a known topic, the hint ends with `see: downcroc -h campaign`. This mapping
lives in one table, not scattered through commands.

---

## 9. The input contract

This is the contract the daemon already accepts. Ticket 09 makes it discoverable and printable.
Nothing here changes the parser's behaviour except where noted.

### 9.1 Detection

The daemon decides by content, not by extension:

| First non-space byte | Kind |
|---|---|
| `{` or `[` | JSON campaign |
| anything else | CSV, requires `--template` |

A JSON file is read as UTF-8. A file above `intake.max_file_bytes` (default 64 MiB) is refused
with the size and the setting that raises it.

### 9.2 JSON campaign

Two accepted shapes.

Bare array: an array of message objects. The campaign key and name default to the file stem.

Object:

```json
{
  "schema": "downcroc.campaign/v1",
  "producer": {"name": "my-script", "version": "1"},
  "campaign": {
    "key": "march",
    "name": "March outreach",
    "routing": {"mode": "auto"},
    "options": {"approval": "review"}
  },
  "messages": [],
  "followups": []
}
```

Top-level keys: `schema`, `producer`, `campaign`, `messages`, `followups`. Anything else is an
error with the field path.

`schema` is optional and defaults to `downcroc.campaign/v1`. Any other value is refused with
"this daemon understands downcroc.campaign/v1".

`producer` is free-form metadata, stored with the campaign and never interpreted.

`campaign` keys:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `key` | string, 1-128 | file stem | stable identifier |
| `name` | string, 1-200 | key | display name |
| `routing` | object | `{"mode":"auto"}` | how messages bind to accounts |
| `options` | object | see below | campaign policy |

`campaign.routing`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `mode` | `auto` or `fixed` | `auto` | auto spreads over connected accounts; fixed uses one |
| `account` | account id | none | required when mode is `fixed` |
| `include` | array of account ids | empty | restrict auto routing to these |
| `exclude` | array of account ids | empty | remove these from auto routing |

Routing is a campaign field, not a message field. `account` on a message is not part of the
contract: it is rejected with `unknown_field` and a hint that names
`campaign.routing.account`. The `--account ID` flag is the CLI spelling of fixed routing and
writes `campaign.routing = {mode = "fixed", account = "<id>"}` before validation, so the file
and the flag cannot disagree. `include` and `exclude` stay file-only; the flag covers the common
case and the contract covers the rest.

A campaign whose routing resolves no connected account is invalid at preview, not at submit.
`batch validate --account ID` performs the same check offline against the accounts in the local
database when one exists.

`campaign.options`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `approval` | `review` or `auto` | `review` | hold for approval, or send when due |
| `suppress_replies` | boolean | `true` | skip anyone who already replied |
| `reply_window_days` | integer | `60` | how long a reply suppresses a follow-up |
| `not_before` | ISO 8601 timestamp | none | do not send before this time |
| `stop_on` | array of `reply`, `bounce` | both | reasons to stop a follow-up chain |
| `allow_duplicates` | boolean | `false` | permit the same address twice |

`messages` is a non-empty array, at most `intake.max_messages` (default 10,000).

Message object:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `to` | object | yes | `{"email": "...", "name": "..."}` |
| `to.email` | string | yes | a valid address |
| `to.name` | string | no | display name |
| `subject` | string | yes | 1-998 characters |
| `text` | string | one of text/html | plain body, at most `intake.max_body_bytes` |
| `html` | string | one of text/html | HTML body, same limit |
| `key` | string | no | 1-128, defaults to `m<N>` |
| `reply_to` | string | no | a valid address |
| `attachments` | array of strings | no | relative paths inside the campaign directory |
| `followups` | object | no | per-message overrides keyed by step |
| `x-*` | any | no | reserved for producers, ignored by downcroc |

Attachment rules: relative only, no `..`, must resolve inside the campaign file's directory,
must exist, at most `intake.max_attachment_bytes` each (default 25 MiB).

Duplicate addresses are an error unless `campaign.options.allow_duplicates` is true. Duplicate
message keys are an error. Unknown fields are errors, except keys beginning `x-` and the known
mail headers listed in `IGNORED_HEADERS` (`from`, `cc`, `bcc`, `date`, `message-id`,
`in-reply-to`, `references`, `account`, and similar), which are reported as ignored rather than
fatal.

Follow-up step object, in top-level `followups`:

```json
{
  "key": "day3",
  "after_days": 3,
  "when": "no_reply",
  "subject": "Following up",
  "text": "Just checking in.",
  "require_approval": false
}
```

| Key | Type | Required | Meaning |
|---|---|---|---|
| `key` | string, 1-128 | yes | step id, unique |
| `after_days` | integer, 1-365 | yes | delay after the parent send |
| `when` | `no_reply` or `always` | no, default `no_reply` | condition |
| `subject` | string | no | defaults to the parent subject with `Re:` |
| `text` | string | one of text/html | body |
| `html` | string | one of text/html | body |
| `require_approval` | boolean | no, default `false` | hold this step for review |

Per-message override, in `messages[].followups.<step>`:

```json
{"day3": {"skip": true}}
{"day3": {"subject": "A different subject", "text": "A different body"}}
```

Allowed keys: `subject`, `text`, `html`, `skip`. Unknown step ids are errors.

### 9.3 CSV plus a template

CSV rules:

- The header is required and must contain `email`, case-insensitive.
- Duplicate headers are ambiguous and refused.
- Every row must have the same cell count as the header.
- `email` must be a valid address. Invalid rows produce an issue with the row number.
- Duplicate addresses are skipped and counted, not fatal.
- Other columns become template variables. `name` is used for the recipient display name when
  present.
- The delimiter is sniffed from `,`, `;`, and tab.
- `from`, `cc`, `bcc`, `date`, `message-id`, `in-reply-to`, `references`, `account` columns are
  ignored and reported.
- Every variable used in the template must be supplied by a column or by `template.toml`
  defaults. Missing variables are errors naming the variable and the row.

Template directory: `<config>/templates/<name>/`, where name matches
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.

```
template.toml
body.txt
body.html      optional
assets/        optional files referenced by attachments
```

`template.toml`:

```toml
subject = "Hello {{name}}"
reply_to = "you@example.com"
attachments = ["deck.pdf"]

[defaults]
name = "there"
```

| Key | Type | Required | Meaning |
|---|---|---|---|
| `subject` | string | yes | rendered with variables |
| `defaults` | table of strings | no | fallback values |
| `reply_to` | string | no | reply address |
| `attachments` | array of strings | no | paths under `assets/`, no `..` |

Variable syntax is `{{ name }}`. Names are matched case-insensitively against columns and
defaults. Built-in variables: `email`, `batch_name`, `date` (UTC, `YYYY-MM-DD`).

### 9.4 Limits

| Limit | Setting | Default |
|---|---|---|
| messages per campaign | `intake.max_messages` | 10,000 |
| body bytes per message | `intake.max_body_bytes` | 1,000,000 |
| attachment bytes | `intake.max_attachment_bytes` | 26,214,400 |
| input file bytes | `intake.max_file_bytes` | 67,108,864 |
| preview sample | `intake.sample_count` | 5 |

### 9.5 Path resolution

The CLI resolves every path before sending it:

1. Expand `~`.
2. Make absolute against the caller's cwd.
3. Check existence and readability client-side, so the error names the caller's path.
4. Send the absolute path.

The daemon still resolves its own relative paths for direct API callers. This is documented in
`02-api-contract.md`.

### 9.6 Worked example: one message

`hello.json`:

```json
[
  {
    "to": {"email": "ana@example.com", "name": "Ana"},
    "subject": "Hello",
    "text": "Hi Ana,\n\nThis is a test.\n"
  }
]
```

```
downcroc batch validate hello.json
downcroc batch submit hello.json --approve none
downcroc review
```

### 9.7 Worked example: CSV plus template

`templates/intro/template.toml`:

```toml
subject = "Hello {{name}}"
[defaults]
name = "there"
```

`templates/intro/body.txt`:

```
Hi {{name}},

I wanted to ask about {{topic}}.
```

`people.csv`:

```csv
email,name,topic
ana@example.com,Ana,invoices
bo@example.com,Bo,shipping
```

```
downcroc batch validate people.csv --template intro
downcroc batch submit people.csv --template intro
```

### 9.8 Worked example: follow-up

```json
{
  "schema": "downcroc.campaign/v1",
  "campaign": {"key": "march", "name": "March", "options": {"approval": "review"}},
  "messages": [
    {"key": "a", "to": {"email": "ana@example.com"}, "subject": "Hello", "text": "Hi"}
  ],
  "followups": [
    {"key": "day3", "after_days": 3, "when": "no_reply", "text": "Just checking in."}
  ]
}
```

`batch show <id>` prints the step id `day3`, which is what `batch followup <id> <path> --step
day3` expects for a manual follow-up batch.

---

## 10. Discovery and validation commands

### 10.1 `batch schema`

Human output: the full contract as readable sections, with field tables, defaults, and one
example per kind. Paged only when interactive.

`--json`: a JSON Schema (draft 2020-12) for the campaign object, plus a `csv` section that
describes required headers, and a `template` section that describes the manifest. JSON Schema
cannot express variable coverage across a CSV and a template, so those rules stay in
`batch validate` and are described in `x-downcroc-rules`.

The schema is generated from the same field registry that `batch validate` uses. There is one
source of truth, so the schema cannot drift from the parser.

### 10.2 `batch example`

| Invocation | Writes |
|---|---|
| `batch example` | prints a one-message campaign to stdout |
| `batch example --kind json` | same |
| `batch example --kind followups` | a campaign with a follow-up step |
| `batch example --kind csv` | a CSV with an `email` header and a name column |
| `batch example --kind template` | `template.toml` and `body.txt` for the CSV example |
| `batch example --write DIR` | writes a complete, validated set into DIR |

The JSON example prints by default so a person can pipe it. `--write` writes files and prints
their paths and the next command. Every example validates against `batch validate` in a test.

### 10.3 `batch validate PATH [--template NAME|PATH] [--account ID]`

Runs the same parser as the daemon, in the CLI process:

- No daemon, no token, no vault, no network.
- Expands paths client-side.
- Reads limits from the config when it exists, and from schema defaults when it does not.
  It never creates a config file, a vault, or a database.
- Prints every issue with `row`, `key`, `field`, `code`, and message.
- Prints warnings and ignored headers.
- Prints a summary: `valid: 240 messages, 3 follow-up steps, 2 warnings`.
- Exit 0 when valid, 1 when invalid, 2 on usage.
- `--json` emits `{"valid": bool, "total": n, "issues": [...], "warnings": [...],
  "ignored": [...], "campaign": {...summary...}}`.

`--account ID` is the offline twin of the daemon's routing check. When a local database exists it
verifies that the account exists and is connected; when there is no database it reports the check
as skipped rather than passing it. It never opens the vault or a credential.

A template argument is a name or a path (D28). A path is read directly and must contain
`template.toml`.

`batch submit --dry-run` performs the same work through the daemon, including routing
assignment against real accounts, and prints the preview plus the issues. It does not write a
batch. A dry run whose fixed account is not connected fails.

### 10.4 `template list|new|show|validate`

- `list`: name, subject, variable count, attachment count, path. Empty state says
  `no templates in <dir>, create one with: downcroc template new intro`.
- `new NAME`: refuses to overwrite. Writes `template.toml`, `body.txt`, `assets/`. Prints the
  path and the next command. The body uses one variable with a default so it validates as-is.
- `show NAME`: manifest, variables used, attachments, rendered sample with defaults.
- `validate NAME|PATH`: parse and render every variable with defaults, report missing defaults,
  unused defaults, empty subject, and attachment problems. Offline.

### 10.5 `--json` completeness

Every command that has human output also emits JSON, including errors:

| Command | JSON |
|---|---|
| `init` | state found, steps run, result |
| `send` | draft path, validation, preview, batch |
| `review` | pending batches with counts |
| `status` | one object per line in the human screen |
| `doctor` | `{"ok": bool, "checks": [{"name","ok","detail","fix"}]}` |
| `batch schema` | JSON Schema plus extensions |
| `batch example` | `{"files": [...]}` or the example object |
| `batch validate` | validity, issues, warnings, summary |
| `template ...` | template objects |
| `backup`, `restore`, `account delete`, `mail attachment` | result objects, errors on stderr |
| every list | items plus `total`, `limit`, `offset` |
| every error | `{"error","message","status","hint","fields","details"}` on stderr |

JSON is never mixed with human text on stdout. Progress and prompts go to stderr.

---

## 11. Preview truth

`PreviewOut` gains:

| Field | Meaning |
|---|---|
| `total` | messages in the campaign |
| `valid` | messages that passed validation |
| `sampled` | messages included in the preview |
| `sample_limit` | the configured sample count |
| `warnings` | non-fatal issues |
| `ignored` | ignored headers and fields |
| `routing` | mode, account, and per-account assignment counts |
| `followups` | step ids, delays, conditions |
| `duplicates` | addresses skipped as duplicates |
| `attachments` | count and total bytes |

Human preview:

```
campaign   March outreach (march)
kind       json
messages   1,240 total, showing 5
approval   review (held until approved)
routing    fixed, ana@example.com (acct_...), 1,240 messages
followups  day3 after 3 days when no reply, day7 after 7 days when no reply
warnings   2
ignored    cc (1,240 rows)

sample
  ana@example.com  Hello          12:04
  ...
```

Rules:

- `ignored` and `warnings` print before the sample table, never after it, so a silently dropped
  field cannot be missed while reading the rows (D42).
- Routing prints the resolved account or accounts with per-account counts. `account -` is never
  printed: a campaign with no resolvable account is invalid and exits 1.
- `--account ID` overrides the file to `fixed` for that account and prints
  `routing fixed by --account`.
- A fixed account that is missing, paused, or without a credential is a preview error with the
  account id and the fix, not a later `account_unavailable` at submit (D52).

`--all` shows every message and is explicit about the cost. `--key` keeps working.

---

## 12. Output rules

### 12.1 Tables

- Width from `shutil.get_terminal_size`, capped at 120 unless `--wide`.
- IDs, addresses, states, codes, timestamps: never truncated. If a table cannot fit, drop
  lower-value columns and say which were dropped, rather than clipping a value.
- Free text (subject, error message, path): truncated to the remaining width with
  `... (+N chars)`.
- `--wide` uses the full terminal width and truncates nothing except newlines.
- `--full` is accepted on record views and disables all truncation.
- A table with no rows prints a specific empty state, never a header alone.

### 12.2 Record views

`record()` prints one key per line. Values containing newlines are indented under the key.
Long values wrap at the terminal width unless `--full`, in which case they print whole.

### 12.3 Lists and paging

- Add `offset` to `GET /api/jobs`, `GET /api/batches`, and `GET /api/failed`.
- Add `X-Total-Count` to every list response.
- CLI footer: `showing 1-100 of 12,043  next: --offset 100`.
- Human output pages through `$PAGER` only when interactive and the output exceeds a screen.
  `--no-pager` and `NO_PAGER` disable it. Prompts never run inside a pager.
- `--limit` maximum stays at the API's bound; the CLI explains when a larger value is refused.

### 12.3.1 Filters are validated, never guessed

A filter that names a state, folder, date, or account is checked before the request. A value
outside the allowed set is a usage error: exit 2, the accepted values printed, and no request
sent. An identifier that is well formed but unknown is `not_found`: exit 1, the id echoed.

| Input | Wrong value | Never acceptable |
|---|---|---|
| `--state` on `job`, `batch`, `failed` | `nonsense` | an empty table and exit 0 |
| `--folder` on `mail` | `NOPE` | an empty table and exit 0 |
| `--account` on `stats`, `job`, `batch` | `acct_missing` | zeros and exit 0 |
| `--since`, `--from`, `--to` | `nonsense` | an empty table and exit 0 |
| `--limit` | `0`, `-1`, `501` | the whole log, or a silent clamp |

`argparse` `choices` supplies the enum values so `-h` lists them. The same parser is used by the
API, so a value the CLI accepts cannot be one the daemon silently ignores (D61, D62).

### 12.4 Empty states

| Command | Empty output |
|---|---|
| `account list` | `no accounts yet, add one with: downcroc account add` |
| `provider list` | never empty; the declarations ship with the package |
| `batch list` | `no batches, send one with: downcroc send` |
| `job list` | `no jobs match` |
| `failed list` | `no failures` |
| `mail list` | `no messages in <folder>` |
| `logs` | `no log file at <path>` (exit 1) or `no events match` (exit 0) |
| `template list` | `no templates in <dir>, create one with: downcroc template new intro` |
| `batch preview` | never empty; a campaign with no messages is invalid |

### 12.5 Colour and glyphs

- `NO_COLOR`, `TERM=dumb`, `--color never`, and non-TTY stdout disable colour.
- Colour never carries meaning alone. Every state also has a word.
- Three tones, and nothing else: green for `connected` and `sent`, red for `not signed in`
  and failed checks, yellow for warnings. No accent colour on ordinary text.
- Every action result uses one shape: `[ok] connected`, `[fail] not signed in`, and a plain
  `checking ... 1.2s` while the work is running. The bracket label, the glyph, and the colour
  always agree.
- Glyphs default to ASCII. `--glyphs nerd`, `DOWNCROC_GLYPHS=nerd`, or
  `downcroc config set cli.glyphs nerd` enables the Nerd Font set. `init` asks once, default no.
- The glyph set is defined in Appendix B. Glyphs never replace a word that is needed to
  understand a line.

---

## 13. Errors and exit codes

### 13.1 Rendering

One renderer for every command:

```
error: <code>: <message>
  hint: <hint>
  field: <path>: <message>
  detail: <key=value>
```

- `hint` and `details` come from the server envelope and are no longer dropped.
- Validation issues from `batch validate` print one line each, then a count.
- Client-side errors (missing file, bad path, refused confirmation) use the same shape.
- `--json` prints the error object on stderr and nothing on stdout.
- `argparse` errors are routed through the same renderer (D69). A missing flag or an invalid
  choice prints one line and exits 2, not a usage block:

```
error: usage: --limit must be at least 1
  hint: downcroc job list -h
```

- A terminal is required for a password prompt. Without one, no prompt is attempted and no
  traceback is possible:

```
error: no_terminal: no terminal for a password prompt
  hint: pass --password-stdin or --password-file PATH
```

- Vault throttling has its own code, so a script can wait instead of retrying blindly:

```
error: vault_throttled: too many attempts, try again in 3.3s
  detail: retry_after_s=3.3
```

- A daemon that does not answer becomes one error instead of a hung terminal:

```
error: daemon_timeout: no response after 10.0s
  hint: check `downcroc service status`, or raise --timeout
```

### 13.2 Exit codes

| Code | Meaning |
|---|---|
| 0 | the requested action succeeded, including a no-op that reports current state |
| 1 | the action failed, or a health check is unhealthy, or the user cancelled a destructive action |
| 2 | usage error, unknown command, unknown topic, invalid flag combination, invalid enum or limit |
| 130 | interrupted with Ctrl-C |

Specific:

- `auth status`: 1 when not accepted or unreachable.
- `service status`: 1 when `stopped` or `stale`, 0 when `running`.
- `doctor`: 1 when any check fails.
- `logs`: 1 when the log file is missing, 0 when it exists and has no matching events.
- `validate`: 1 when invalid.
- `restore --dry-run`: 0 when the bundle is valid, 1 when it is not.
- `vault unlock`: 0 when it unlocked or was already unlocked, 1 on a bad password or throttle.
- `vault init`: 0 when it created the vault, 1 when one already exists.
- A declined confirmation prints `cancelled` and exits 1, so a script cannot mistake a decline
  for success.
- `--json` does not change exit codes.

---

## 14. Confirmation model

| Action | What is shown before | Flag to skip | Notes |
|---|---|---|---|
| `account delete` | address, last activity, job count if available | `--yes` | prompts on a TTY; refuses without `--yes` when not a TTY |
| `batch cancel` | id, name, counts by state, how many already sent | `--yes` | sends already in flight are not recalled |
| `batch approve all` | id, remaining count, accounts | `--yes` | interactive flow asks in words |
| `batch submit --approve all` | total, accounts, approval mode | none (the flag is the consent) | interactive asks separately |
| `failed retry-all` | count, accounts, retryable versus permanent | `--yes` | |
| `stats prune` | cutoff date, rows to remove if known | `--yes` | report after |
| `restore` | manifest, current data path, replacement path | `--yes` | typed `restore` in interactive |
| `service uninstall` | unit path, manager, "data stays" | `--yes` | |
| `job create --send` | recipient, subject | `--yes` | |
| `job send` | recipient, subject, account | `--yes` | |
| `job create` on a pending account | the account state and what it means | `--force` | refuses by default; the warning stays in the output |
| `provider remove` | id, declaration path, accounts that would break | `--yes` | refuses while any account uses it |
| `vault lock` | none | n/a | reversible, no prompt |
| `vault lock --forget` | that the stored password is deleted and the vault is locked; the master password is unchanged | n/a | one line after, with `vault keyring enable` as the way back |
| `vault keyring disable` | the store item is deleted; unlocking will prompt again | n/a | the vault password is unchanged |
| `vault init` | that the password cannot be recovered, and that an existing vault is never replaced | n/a | double prompt, mismatch re-prompts |
| `mail attachment` overwrite | target path | `--force` | |
| `backup` overwrite | target path | `--force` | |
| `init` on an existing install | paths found, steps that will be skipped | `--yes` | never overwrites the vault |

Rules: confirmations go to stderr, default to no, and accept only `y`/`yes` and `n`/`no`.
Anything else re-prompts. In `--no-input`, a missing `--yes` is an error, not a prompt.

---

## 15. Provider truth

`GET /api/providers` already exposes `auth_kind`, `oauth_configured`, `imap_host`, `smtp_host`,
and `notes`. The CLI uses all of it. `account providers` is kept as an alias of
`provider list` so no existing invocation breaks.

Declarations are read from the package, then `~/.config/downcroc/providers.toml`, then
`~/.config/downcroc/providers.d/*.toml`, later winning. `provider show` prints the merged
result and the file that supplied each section. `provider add` writes the user file, mode
`0600`, through the same merge path, so a command-written declaration and a hand-written one
cannot diverge (D50).

`account providers`:

```
  provider            label          door           ready   note
  gmail               Gmail          OAuth client   no      set oauth_client_id and oauth_client_secret
  gmail-app-password  Gmail          app password   yes
  microsoft           Microsoft 365  OAuth client   no      set oauth_client_id and oauth_tenant
  generic             Other IMAP     app password   no      set imap_host and smtp_host
```

Rules:

- `ready` is computed: app-password providers are ready when they have hosts; OAuth providers
  need both a client id and a client secret (and a tenant for Microsoft); generic needs hosts.
- `gmail` and `gmail-app-password` are two declarations of one mailbox provider.
  `account providers` lists both because they are two real registry entries. `account add` and
  `init` fold them into one `Gmail` row and ask which door to use.
- Empty hosts print `not set`, never `:993`.
- `notes` prints under the table for the selected provider, not as a clipped column.
- Selecting an unready provider in `account add` explains the exact fix and offers to open the
  config file. It does not create an account that can never connect unless the user explicitly
  chooses "create anyway".
- The custom mailbox branch of `init` and `account add` writes a complete declaration through
  the same registry merge path used for hand-written files: `[providers.<id>]` with hosts,
  ports, TLS modes, and username. It writes mode `0600`, never writes a password, and shows the
  file and key it wrote so the user can edit them later.
- Provider setup is checked by `doctor`: missing client id, missing tenant, empty hosts, an
  unsupported auth kind, and a declaration that fails to parse.

Gmail has two doors. The prompt asks which one and preselects neither.

**Door 1, app password.** Two minutes, no browser, no console.

1. Turn on 2-Step Verification on the Google account.
2. Generate an app password at `https://myaccount.google.com/apppasswords`.
3. `downcroc account add`, choose Gmail, choose `App password`, paste it.
4. The CLI checks IMAP at `imap.gmail.com:993` and prints `connected` with the sent folder.
5. The test message proves SMTP.

What the prompt says about this door: it needs 2-Step Verification, Google can withdraw it,
and a Workspace administrator can disable it for the whole domain.

**Door 2, OAuth client.** One console trip, no dependence on app passwords existing.

1. Create a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen as External, and add your address as a test user while
   the app is unpublished. Scope: `https://mail.google.com/`.
3. Create credentials, OAuth client ID, type `Desktop app`.
4. Give the CLI both values. It writes them to `~/.config/downcroc/providers.toml` under
   `[providers.gmail]` with mode `0600`:

```toml
[providers.gmail]
oauth_client_id = "....apps.googleusercontent.com"
oauth_client_secret = "..."
```

5. The CLI opens the browser, waits for `http://127.0.0.1:<port>/callback`, and prints
   `connected`.
6. The unpublished client issues seven-day refresh tokens. When one expires the account becomes
   `needs_reauth`, and the fix is the same connect step. Publishing the app removes the limit
   and moves the verification burden onto whoever owns the client id.

Both values are required. Google's token endpoint rejects the exchange when the secret is
missing, so asking only for the client id produces a failure at the last step (D49).

Why no default: each door has a cost the project cannot remove. App passwords are faster but
depend on provider policy staying permissive. OAuth is slower to set up but does not depend on
app passwords continuing to exist. A default would turn that trade-off into advice, and the
advice would be wrong for some accounts. The prompt states both costs and lets the user pick.

Facts the help topic states, because they change what a user should choose:

| Fact | Consequence |
|---|---|
| Gmail app passwords require 2-Step Verification | An account without 2SV cannot use door 1 |
| Workspace moved third-party access to OAuth on 2025-03-14, with an app-password exception | A Workspace account may have door 1 disabled by its administrator |
| A 2026 app-password phase-out is claimed by secondary sources and not confirmed by a primary Google announcement | Door 1 is offered as working today, not as a guarantee |
| An unpublished OAuth client gets seven-day refresh tokens | Door 2 needs one more step before it is durable |
| Google requires verification for the restricted `https://mail.google.com/` scope | Shipping one shared client id is a project commitment, not a CLI change (D46) |

---

## 16. Status and doctor

Covered as flows in 6.6. Implementation notes:

- `status` composes existing endpoints: `/api/status`, `/api/vault`, `/api/accounts`,
  `/api/batches?state=...` or stats, `/api/failed?limit=1`, and the service file.
- It must not print `ok` for anything it did not check.
- `doctor` is the only command allowed to run checks that write nothing. It never repairs
  without an explicit subcommand later.
- Both work when the daemon is stopped: they report what can be checked from disk.
- `status --json` and `doctor --json` are stable enough for monitoring.

---

## 17. Paths and files

One helper, `cli/paths.py`:

```
resolve_input(path, *, must_exist=True) -> Path
resolve_output(path, *, directory_ok=False, default_name=None) -> Path
expand_editor_path(path) -> str
read_secret_file(path) -> str
```

Rules per command:

| Command | Path kind |
|---|---|
| `batch validate|preview|submit`, `batch example --write` | input, or directory for write |
| `batch followup` | input |
| `job create --text-file|--html-file` | input |
| `backup [PATH]` | output; existing directory or trailing separator means generated name |
| `restore PATH` | input, must be a file |
| `openapi -o PATH` | output; `-` means stdout; parent must exist unless `--mkdir` |
| `mail attachment -o PATH` | output; directory means original filename |
| `template` | names resolved under `<config>/templates`, or a path when one is given |
| `vault unlock|init --password-file PATH` | input, must be a regular file; mode `0600` or tighter |
| `provider` | ids; declarations under `<config>/providers.toml` and `<config>/providers.d/` |
| `send` | input plus drafts under `<data>/drafts` |

All paths in output are absolute. All paths echoed back are the resolved path, so the user can
copy them.

`--password-file` refuses a path that is world-readable, a symlink, or a directory, and never
echoes the contents. This is the recommended form for systemd `LoadCredential` and container
secret mounts (D57).

`--timeout` defaults to `cli.timeout_s` in the config, 10 seconds, with a 60 second ceiling. It
covers connect, read, and write. A value of `0` disables the read timeout and prints a warning,
because it restores the hang that D60 exists to remove.

---

## 18. Implementation

### 18.1 Dependencies

No new prompt library. `cli/ui/` is built on the standard library: `input()` for numbered
menus and free text, `getpass` for masked secrets, `shutil.get_terminal_size` for width, and
`subprocess` for the editor. This keeps TTY detection, masking, and cancellation in one small
module with no transitive dependency, and avoids a second interactive stack beside the
existing table renderer.

`keyring` remains an optional dependency, imported lazily by `runtime/keyring.py` and used
only for the vault password. On Linux it brings `jeepney` and `secretstorage` for Secret
Service; on Windows it uses the standard library and Win32 calls. Install it without
`keyrings.alt`: a file or plaintext backend is refused at runtime, because a second password
to protect the second password defeats the purpose. When the package or backend is absent,
the command reports `unavailable` and the prompt takes over.

Do not use `rich`. The existing table renderer stays; it is small and predictable, and adding a
second rendering stack would mean two visual languages.

`keyring` is read through a single adapter so non-interactive commands and the daemon never
pay for it, and a missing optional import cannot break scripts.


### 18.2 New package

```
src/downcroc/cli/ui/
  __init__.py          exports run_menu, prompt helpers
  session.py           interactive() predicate, glyphs, colour, width, editor
  prompts.py           ask, ask_secret, choose, choose_many, confirm, pick_path
  menu.py              Menu, Item, run loop, breadcrumb, keys, filtering
  render.py            state summaries shared by status and home
  help.py              topic registry, renderer, -h interception
  topics/              one markdown file per topic
  flows/
    first_run.py       init, vault init
    send.py            send, compose, draft writing
    review.py          review
    accounts.py        account menu, add, connect
    providers.py       provider menu, add, edit, remove
    mail.py            mail menu
    failures.py        failures menu
    settings.py        settings menu
    backup.py          backup and restore
    templates.py       template menu
```

Plus:

```
src/downcroc/cli/paths.py        path resolution helper, secret file reader
src/downcroc/runtime/keyring.py  OS credential store adapter, availability probe
src/downcroc/cli/errors.py       argparse error override, one renderer
src/downcroc/cli/help.py         thin re-export for `downcroc help`
src/downcroc/cli/schema.py       the field registry and JSON Schema emitter
src/downcroc/cli/commands/state.py    status and doctor
src/downcroc/cli/commands/send.py     send
src/downcroc/cli/commands/review.py   review
src/downcroc/cli/commands/templates.py
src/downcroc/cli/commands/inputs.py   schema, example, validate
src/downcroc/cli/commands/providers.py   provider list, show, add, edit, remove
src/downcroc/cli/commands/vault.py       init, idempotent unlock, password file
```

Size rules from `AGENTS.md`: every file under 400 lines. A flow that grows past that splits by
action, not by shortening lines.

### 18.3 Wiring

- `cli/main.py` gains the new dispatch entries and the global flags.
- `cli/parser.py` gains the new commands, help on every flag, and epilogs. If it passes 400
  lines, split into `parser/` with one module per command group, re-exporting `build_parser`.
- `cli/client.py::_raise` keeps the whole envelope. `CliError` gains `hint` and `details`.
  The `httpx` client gets explicit connect, read, and write timeouts from `--timeout` or config.
- `cli/output.py` gains width-aware rendering, `--wide`/`--full` context, list footers, and
  unchanged `json_out`.
- `cli/context.py` gains `Paths` for templates and drafts; `load()` stays.
- `cli/paths.py` owns every path and secret-file read, so `input_unreadable` is raised in one
  place (D26, D64).
- `runtime/keyring.py` owns the credential store: availability probe, backend allowlist,
  `get`/`set`/`delete`, and a typed result for each failure. It takes the vault path as the
  account name, so a second installation never overwrites the first. The daemon never imports it.
- `core/vault_service.py` gains `init` and an idempotent `unlock`, and returns `vault_throttled`
  with `retry_after_s`. The API gains `POST /api/vault/init` and keeps `unlock` compatible.
- `core/providers` gains write and validate paths for `provider add|edit|remove`, reusing the
  registry merge. No new storage.
- `runtime/service/lifecycle.py::start` gains progress callbacks and a timeout. `service restart`
  is `stop` then `start`, and does not touch data.
- `cli/parser.py` sets `choices` for every enum and `type=` validators for limits and dates, so
  invalid filters cannot reach the daemon (D61, D62).
- No change to any `core/` send path for phase A or C except D6, D52, and D14.
- Offline validation imports `core.inputs` and `core.batches.source.CampaignReader` with a
  no-op logger and a settings object built from config defaults. It must not construct the
  vault, the store, or the HTTP app.

### 18.4 Help and docs generation

`cli/schema.py` owns field definitions. `batch schema`, `batch validate`, the help topics, and
the docs book all read it. One field table, four renderings:

1. Human tables.
2. JSON Schema.
3. Markdown for `docs/` and the plan.
4. The error messages used by the parser where practical.

The parser currently has its own field checks. Ticket 09 does not have to rewrite the parser
to use the registry, but the registry must describe the same rules and a test must compare
them: every field accepted by the parser appears in the registry, and every registry rule has
a fixture that exercises it.

---

## 19. Tickets

### 19.1 Ticket 09, phases

One ticket, three phases, one commit each. The phases are ordered so the product is usable
after A, truthful after C, and documentable after B.

**Phase A: interactive shell (human path)**

- `interactive()` and global flags, including `--timeout`.
- `init`.
- `vault init`, the double prompt, and the `isatty` guard on every password prompt.
- Credential store: the init question, silent unlock, `vault keyring status|enable|disable`,
  `vault lock --forget`, and the one-line fallback when the store is unavailable (D75).
- Bare-command state handling.
- Account menu, picker, sign-in method prompt with no default, auth-kind-aware connect,
  attempt progress, vault password confirmation.
- `provider list|show|add|edit|remove` and the `account add` host and OAuth flags (D50, D51).
- The connect result contract: check line, provider reason, hint, retry menu (section 6.3.1).
- Send, review, mail, failures, settings menus, calling existing handlers.
- `$EDITOR` for bodies.
- Confirmation helper used by every destructive action in the table.
- `service start` progress and `service restart`.
- Next-step hints on every mutating command (D70).
- `account watch` as a TTY toggle (D72).
- Standard-library prompt layer wired, glyph set, ASCII fallback.

Acceptance:

1. On an empty `HOME`, `downcroc init` in a PTY reaches a running daemon and one connected
   fake account with no flag knowledge.
2. `downcroc account add` in a PTY lists providers and creates the account.
3. `downcroc send` in a PTY submits a fixture campaign and prints the batch id.
4. `downcroc review` in a PTY approves a held batch.
5. `downcroc` with the daemon stopped offers to start it; with it running, does not tell the
   user to start it.
6. Every prompt is skipped with `--json`, `--no-input`, piped stdin, or `CI=1`; a missing value
   produces an error naming its flag.
7. Gmail offers both doors, preselects neither, and the app-password door reaches `connected`
   against the fake IMAP server. The OAuth door never asks for an app password.
8. `restore` shows the manifest and does nothing until confirmed.
9. A declined confirmation exits 1 and changes nothing.
10. A failed app-password connect prints the provider reason and the hint, stores no credential,
    leaves the account `pending`, and offers retry, change method, and exit. The third failure
    stops with the lockout explanation instead of a fourth prompt.
11. A successful connect prints `connected` with the IMAP host and sent folder and does not
    claim SMTP. The test message is what proves sending.
12. `provider add fastmail` on a fresh home writes a declaration, `provider list` shows it as
    ready, and `account add --provider fastmail` connects against the fake IMAP server with no
    hand-edited file.
13. `vault init` twice refuses the second call and leaves the first vault intact. `vault unlock`
    on a missing vault names `vault init`.
14. `vault unlock` with stdin closed prints `error: no_terminal` and no traceback.
15. `service start` prints `starting ...` before the health wait, and `service restart` returns a
    running daemon with the same data directory.
16. `account add` prints a `next:` line naming `account connect`.
17. `vault init --keyring` against a fake store makes the next `vault unlock` succeed with no
    prompt and print `unlocked (system credential store)`.
18. `vault keyring disable` deletes the item, and the next unlock prompts again.
19. With no store available, `init` prints one line and creates the vault anyway; `--keyring`
    fails with `keyring_unavailable` instead of silently prompting.
20. `--no-input` without `--keyring` neither reads nor writes the store, and `vault lock
    --forget` removes the item and locks.

**Phase B: input contract (discovery path)**

- Field registry and JSON Schema.
- `batch schema`, `batch example`, `batch validate`, `batch submit --dry-run`.
- `template list|new|show|validate`, with a name or a path.
- Preview totals, warnings, ignored fields, routing, follow-ups.
- `--account` on preview, submit, followup, and validate, and rejection of a per-message
  `account` (D52).
- Preview fails when routing resolves no connected account.
- Follow-up step ids in `batch show`.
- Flag help and example epilogs, including `--key` on `submit`.
- `-h <topic>` and `help`.
- Path resolution for input and template paths.
- The combination checks (`--template` on JSON, `--step` without steps).

Acceptance:

1. With no daemon and no vault, `batch validate` on a valid file exits 0 and prints totals.
2. With no daemon, an invalid file prints every issue with row, key, and field, and exits 1.
3. `batch example --write DIR` produces files that validate without edits, for every kind.
4. `template new intro` then `batch validate` of the generated CSV example exits 0.
5. `batch preview` of a 20-message campaign prints `20 total, showing 5`.
6. `batch schema --json` is valid JSON Schema and includes every field the parser accepts.
7. `--template` with a JSON file fails before reading it, naming the conflict.
8. `-h` on any command shows help for every flag; an automated test enforces this.
9. A per-message `account` is rejected with a hint naming `campaign.routing.account`.
10. `batch preview --account <connected id>` prints `routing fixed` and the account address.
11. `batch preview --account <pending id>` exits 1 before any submit.
12. `--template /abs/path` reads that directory and validates, and `template validate /abs/path`
    does the same.

**Phase C: truth fixes**

- Hint and details passthrough.
- Exit codes (`auth status`, `service status`, `doctor`, `logs`, validate, cancel, vault init,
  vault unlock).
- Wide/full output and no truncation of identifiers, including the vault path.
- Provider table and readiness, both Gmail doors, and the client id plus secret pair (D49).
- Stop publishing `smtp_auth_mechanism` until the sender reads it (D48).
- `logs` missing file and the daemon-down hint.
- Validation error wording (`query`, `path`, `body`).
- Client-side validation for states, folders, dates, accounts, and limits (D61, D62).
- Attachment overwrite refusal.
- Path expansion and `input_unreadable` everywhere (D26, D64).
- `--json` on `backup`, `restore`, `account delete`, `mail attachment`.
- List totals via `X-Total-Count`, offsets for jobs, batches, failures.
- `status` and `doctor`, including the keyring line and the credential-store check.
- `job create` and `job send` account preflight (D63).
- `job create` refuses a batch that does not exist, or creates a real one.
- Glossary and display labels.
- `account attempt --wait` progress.
- `vault unlock` idempotent; `vault_throttled` with `retry_after_s`; `--password-file` and the
  extra-line rule (D55, D56, D57).
- `vault` and `account list` no longer print the stray credential table (D65).
- Watcher off until connected (D66).
- `account show` labelled sections (D67).
- `backup` and `restore` messages, absolute path, one warning (D68).
- `argparse` error renderer (D69).
- `openapi -o` parent check (D71).
- Request timeouts (D60).

Acceptance:

1. A server error with a `hint` prints the hint.
2. `auth status` with the wrong token exits 1.
3. A 200-character subject appears whole under `--full` and with a length hint without it.
4. An id, address, and code are never truncated at any width.
5. A 250-row `job list` prints `showing 1-100 of 250`.
6. `account providers` shows the Gmail OAuth row as not ready with the file and both keys, and
   the Gmail app-password row as ready. `smtp_auth_mechanism` is no longer in the response.
7. `logs` with no file exits 1 and names the path.
8. `--limit 501` names `limit` as a query parameter, and `job list --state nonsense` exits 2 and
   lists the accepted states.
9. `mail attachment` refuses to overwrite without `--force`.
10. `downcroc status` reports every line truthfully with the daemon stopped and running.
11. `service status` exits 1 for `stopped` and `stale`, and 0 for `running`.
12. `logs --limit 0` exits 2 and does not read the file.
13. `job create` on a `pending` account exits 1 and names `account connect`; `--force` queues it
    with the warning.
14. `job create --text-file /missing` prints `error: input_unreadable` with the absolute path and
    no Python errno.
15. `vault unlock` twice exits 0 both times, the second printing `changed no`.
16. A throttled unlock prints `vault_throttled` and the wait, and `vault status` reports it.
17. `vault unlock --password-file` reads a `0600` file and refuses a world-readable one.
18. `account list` after `vault unlock` prints the account table only once, and `vault unlock`
    prints no credential table.
19. `backup` before the first boot prints `error: no_database` and names `service start`.
20. A missing required flag prints one `error: usage:` line, not an argparse usage block.
21. A daemon that accepts and never answers produces `daemon_timeout` within `--timeout`.
22. `account show` prints labelled `identity`, `sync`, `quota`, and `routing` sections.
23. `status` prints `keyring on (secret service)` or `keyring off`, and `doctor` reports an
    unavailable store as information with a zero exit code.

**Phase P: prefactor for ticket 06**

Separate, tiny, lands before the PyInstaller spike:

- `lifecycle.start` uses `units.launcher()` plus `serve`.
- A test asserts the launcher list under `sys.frozen` is the executable alone and under normal
  execution is `[python, "-m", "downcroc"]`.

The real proof is the ticket 06 smoke test: build the binary, run `service start`, hit health.

### 19.2 Ticket 09b (optional split)

If phase B grows past a reasonable commit, split it into `09b-input-contract.md` containing the
registry, schema, example, validate, templates, preview truth, and follow-up display. Phase A
and C stay in 09. The dependency order does not change.

### 19.3 Ticket 04 handoff

04 starts only after A, B, and C are green. It documents:

- The CLI surface as shipped, generated from the parser and registry.
- The input contract as shipped, generated from the registry.
- The flows as shipped, with the same prompt text.
- Installers and `update` after 07.

Nothing in 04 may describe a flag that is not in the parser or a format that `batch validate`
does not accept. A test in 04 runs the examples in the book.

### 19.4 Commit plan

| Commit | Subject |
|---|---|
| P | `fix(service): start the daemon through the frozen launcher` |
| A | `feat(cli): add interactive menus and first-run setup` |
| B | `feat(cli): add campaign schema examples and validation` |
| C | `fix(cli): report state hints and limits truthfully` |
| C | `feat(cli): add status and doctor` |

Subjects under 72 characters, no bodies, per `AGENTS.md`.

---

## 20. Test plan

### 20.1 Layers

- **Black-box CLI tests** in `tests/`: run the real binary through `uv run downcroc` against a
  real daemon and real HTTP, with fake IMAP, SMTP, and OAuth servers only.
- **PTY tests** for prompts: a stdlib `pty` helper that starts the command in a pseudo-terminal,
  reads until an expected prompt, sends keys, and strips ANSI. No fixed sleeps; wait for
  output. POSIX only; Windows runs the non-interactive equivalents.
- **Offline tests** for schema and validate: no daemon, temporary `HOME`, fixture campaigns.
- **Schema tests**: every registry field has a fixture; every parser field appears in the
  registry; generated JSON Schema validates the examples.
- **Help tests**: every argument has help text; every leaf command has an example; every topic
  referenced by an error hint exists.

### 20.2 Fixtures

```
tests/fixtures/campaigns/
  one.json
  bare-array.json
  followups.json
  invalid-address.json
  invalid-schema.json
  attachments/
    note.txt
  csv/
    people.csv
    missing-email.csv
    bad-rows.csv
  templates/
    intro/{template.toml,body.txt}
```

### 20.3 Determinism

- Fake servers bind ephemeral ports.
- Every test gets a temporary `HOME` and XDG directories.
- Prompt tests assert on stable prompt text, not cursor movement or colour.
- `NO_COLOR=1` and `--glyphs ascii` in tests, plus one test that asserts the Nerd set renders.
- No test depends on an external network or a real mail provider.

### 20.4 Matrix

- Linux: full suite including PTY, plus one credential-store test against a fake Secret Service
  boundary.
- Windows: full suite minus PTY, plus one PowerShell-driven `--no-input` test of `init --json`
  and `batch validate`, and one Credential Manager test that skips when the runner exposes no
  credential service.
- macOS: no leg. Release 1 does not test, package, or support it.

---

## 21. Compatibility

- No flag is removed or renamed in release 1.
- Exit code changes are intentional, and the decision log records them:
  - `auth status`, `doctor`, `logs`, and now `service status` fail when unhealthy.
  - `vault unlock` exits 0 when the vault is already unlocked instead of 1.
  - usage errors keep exit 2 but change shape from an argparse block to `error: usage: ...`.
- `vault init` is new. A script that relied on the first `unlock` creating the vault must call
  `vault init` first. The ticket 04 upgrade notes carry the one-line change.
- `vault unlock` may now succeed without a password when the credential store holds one, which
  is new. `--no-keyring` restores the prompt, and automation that must not touch the store
  should pass it. A first unlock on an existing install has no item until `vault keyring enable`
  is run, so nothing changes by itself.
- `--password-stdin` now rejects a second non-empty line. A caller that piped extra data was
  silently truncated before; the new behaviour is an error, which is the fix.
- `batch submit --approve one|all` keeps its meaning but the help and prompts say what it does.
- `batch preview` now fails when routing resolves no account, where it previously exited 0 and
  printed `account -`. This is the defect being fixed (D52).
- `job create` gains validation for `--batch`; scripts that relied on the ghost `manual` batch
  must pass an existing batch id or use `batch submit`. It also refuses a `pending` account
  unless `--force` is passed.
- Human output changes shape (columns, totals, section labels). Scripts should use `--json`.
  The README and docs say so.
- `--json` output stays additive: new keys may appear; existing keys do not change meaning.
- The API list responses gain a header, not a new body shape, so existing clients are
  unaffected.
- `providers.toml` and `providers.d/` keep their current format. `provider add` writes the same
  shape a hand-edited file uses, so nothing needs migrating.

---

## 22. Documents to update

| File | Change |
|---|---|
| `plan/README.md` | add 13 to the doc map, mark 08 as deferred for release 1 |
| `plan/08-tui.md` | header: deferred, superseded by 13 for release 1 |
| `plan/01-architecture.md` | client layer includes the interactive CLI, not only flags; Linux and Windows support matrix, no macOS |
| `plan/02-api-contract.md` | list offsets and `X-Total-Count`, error envelope as rendered, path resolution, `POST /api/vault/init`, `vault_throttled`, provider write routes |
| `plan/04-security.md` | optional system credential store, its threat model, and the backend allowlist |
| `plan/06-send-pipeline.md` | preview totals, validate, draft campaigns, approval words, routing is campaign-only and `--account` |
| `plan/11-decision-log.md` | Q75 interactive layer, Q76 input contract, Q77 exit and truth contract, Q78 frozen launcher, Q79 provider commands, Q80 vault init, Q81 credential store |
| `plan/12-module-map.md` | `cli/ui/`, `cli/paths.py`, `cli/errors.py`, `cli/schema.py`, `runtime/keyring.py`, new command modules |
| `README.md` | release status and the new first-run path (ticket 04 completes it) |

---

## 23. Open decisions

Each carries a recommendation, except those marked decided. The ticket can start on a
recommendation and change later; a decided item is settled for release 1.

**Q-A. Fold `batch schema|example|validate` and `template` into 09, or split 09b?**

Recommendation: fold into 09 as phase B. Ticket 04 cannot document an input contract that does
not exist, and the schema registry is what makes the docs generated rather than hand-written.
Split later only if the phase grows past a comfortable review.

**Q-B. Guided compose writes a draft campaign, or calls `job create`?**

Recommendation: a draft campaign under `<data>/drafts/<date>-<slug>/campaign.json`. It is
inspectable, replayable, reusable for a real batch, and uses the path the daemon already
supports. It also removes the ghost `manual` batch from the human path. `job create` stays for
agents.

**Q-C. Does the home menu carry `docs` and `doctor`?**

Recommendation: `status` and `doctor` are rows on the home menu, under a `Status` entry.
`docs` is not a menu row; it is a top-level command and a line in `-h`, because a person in a
menu wants to act, not read a book.

**Q-D. macOS leg advisory or blocking?**

Removed. Release 1 supports Linux and Windows only. The macOS CI leg is deleted rather than made
advisory, because an advisory leg is a test nobody reads for a platform nobody supports. The
darwin fallbacks in `runtime/paths.py` and `runtime/service/units.py` stay in the tree, untested
and without a support commitment. The installer, binary, and release tickets drop their macOS
items, and the `Operating System :: MacOS` classifier leaves `pyproject.toml`. Revisit only if a
real user asks for it.

**Q-E. Account policy editing in 09?**

Recommendation: no. It needs new API routes and a decision about per-account versus global
limits. Release 1 labels the values read-only and explains them. Add `hunt`-style scope note to
the ticket: CLI truth first, new capability second.

**Q-F. A persistent REPL?**

Recommendation: no. Menus cover the flows. A REPL adds a state machine, history, and
completion work with no proven need.

**Q-G. Pager on by default?**

Recommendation: yes when interactive and stdout is a TTY, with `--no-pager` and `NO_PAGER`.
Never inside a prompt flow. The log follow command never pages.

**Q-H. Which Gmail door is the default?**

Decided: none. The prompt asks for the sign-in method with no preselection whenever a provider
has more than one door. Both Gmail doors carry a cost the project cannot remove: app passwords
are two minutes but depend on provider policy, OAuth is one console trip but does not. A default
would encode a bet as advice, and the bet would be wrong for Workspace accounts and for accounts
without 2-Step Verification. Section 15 carries the two flows and the facts behind the choice.

**Q-I. Two Gmail declarations, or a per-account auth kind?**

Decided: two declarations, `gmail` and `gmail-app-password`, folded into one picker row. It
needs no schema change, no migration, and no new service code, because `connect_password` and
the IMAP and SMTP layers already branch on `auth_kind`. A per-account override is cleaner if a
third door appears, and can replace this in release 2.

**Q-J. Provider configuration as commands, or flags on `account add`?**

Recommendation: commands as the primary surface, flags as the script spelling. `provider add`
writes a reusable declaration once; `account add --imap-host ...` serves a one-off. Both go
through the same registry merge. Provider TOML is not moved into `config schema`, because it
holds structure (hosts, ports, TLS, auth kinds) that a flat key/value `config set` cannot
express without inventing a second schema language.

**Q-K. Does `vault init` become mandatory before `unlock`?**

Decided: yes. An implicit create on first unlock is how a typo becomes the permanent master
password, and there is no rekey command in release 1 (D74). `vault init` costs one command and
removes the failure mode. `init` calls it, so the guided path does not get longer.

**Q-L. May the vault password live in the system credential store?**

Decided: yes, opt-in. The complaint behind it is explicit: a second permanent password is one
password too many, and the product exists for people who want to send mail without ceremony.
`vault init` offers to remember the master password, which writes it to Secret Service on Linux
or Credential Manager on Windows. From then on the person types only the OS login password.
downcroc never reads or verifies that login password, because no portable check exists and a
login password change must not lock the vault; the store holds the chosen vault password
instead.

The boundary is stated rather than hidden:

- Only the CLI reads the store. The daemon still starts locked and receives an unlock over the
  API, so the lifecycle in `01` and the token invariant in `04` do not move.
- The store holds the password, never the derived key, and never a mailbox credential.
- The choice is off for `--no-input` unless `--keyring` is passed, removable with
  `vault keyring disable` or `vault lock --forget`, and visible in `vault status`, `status`, and
  `doctor`.
- A missing, locked, or stale item falls back to the prompt with one line. It never fails the
  command and never loops.
- File and plaintext backends are refused. A password manager backend that needs another
  password is not a solution to this problem.
- The security trade is written in `04-security.md`: with the store on, any process in the
  logged-in user session can unlock. The vault still protects a stolen disk or backup, which is
  what it was for.

Revisit the default only if a user study shows the opt-in is missed; the question is asked in
`init` with the recommended choice first, so it is hard to miss.

---

## 24. Risks

| Risk | Mitigation |
|---|---|
| Prompt library breaks in a minimal terminal or on Windows | Lazy import, ASCII fallback, non-TTY path never imports it, Windows test in CI |
| Two code paths drift (menu versus flags) | Menus call command handlers, not their own logic; a test asserts the same result for the menu path and the flag path |
| Schema registry drifts from the parser | Registry/parser parity test plus fixtures for every rule |
| Output changes break scripts | `--json` is additive and documented; human output is explicitly not a contract |
| Preview totals need API changes that grow the ticket | The totals come from the parsed campaign in the daemon, which already has it; only list totals need a header |
| PTY tests are flaky in CI | Wait on exact prompt text, no sleeps, one retry only with a printed dump, diagnostics on failure from `tests/harness/diagnostics.py` |
| `init` does too much and fails halfway | Each step is idempotent and reports state; failure leaves a resumable install and says the next command |
| The interactive layer becomes a second product with its own rules | Every prompt is documented as a front end, and phase A has no new daemon capability except what truth requires |
| The app-password door stops working because the provider withdraws it | The door is labelled as provider policy dependent, the OAuth door is always offered beside it, and the failure lands on `needs_reauth` with a hint that names the switch. No account is built on the assumption that the door survives |
| A user creates an account through a door that is not configured and abandons it | The account stays `pending` and resumable, `doctor` lists it, and `account` offers reconnect or delete |
| `provider add|edit` writes a declaration that the registry cannot parse | Every write is validated by the same loader before it is committed, the previous file is kept beside it, and a failed write prints the field and the backup path |
| Existing installs have a vault but no `vault init` history | `vault init` is only required when no vault exists. An existing vault unlocks exactly as before, and `init` reports `vault exists, locked` |
| A short `--timeout` aborts a legitimately slow backup or restore | The timeout is per request and configurable, `--timeout 0` disables the read timeout with a warning, and long operations print progress so the user knows to raise it |
| `provider remove` deletes a declaration an account still depends on | It refuses while any account references the provider, lists the accounts, and requires `--force` only after they are deleted or moved |
| The credential store is missing, locked, or slow on a server | It is probed once with a short timeout, reported as unavailable in one line, and the prompt takes over. `--keyring` fails loudly for scripts, and nothing else changes |
| A stored vault password goes stale after a manual rekey elsewhere | The failed item is deleted, the prompt appears with a note, and a successful unlock offers to store the new password |
| The credential store silently accepts a file backend | Only Secret Service and Credential Manager are allowlisted; anything else is reported as unsupported and treated as unavailable. `keyrings.alt` is never installed |
| The frozen binary cannot import the store backend | Ticket 06 adds the backend imports to the spec and its smoke test asserts `vault keyring status` answers instead of crashing; the fallback is a prompt, not a failure |
| A user enables the store on a shared machine and forgets | `vault status`, `status`, and `doctor` print the enabled state, the prompt states the trade, and `vault lock --forget` removes it in one command |

---

## Appendix A: help topics and their content

| Topic | Must answer |
|---|---|
| `start` | what downcroc is, install, `init`, where files live, how to stop it |
| `ui` | menus, keys, when prompts are skipped, `--no-input`, `--json`, editor, glyphs |
| `send` | the three sources, validation, preview, approval, what a draft is |
| `campaign` | every JSON field, defaults, limits, duplicates, attachments, follow-ups |
| `csv` | required headers, variables, duplicates, row errors |
| `templates` | directory layout, manifest, variables, defaults, assets, `template new` |
| `followups` | steps, `after_days`, `when`, overrides, approval, reply window |
| `batch` | states, actions, what approve one and all do, cancel, suppression, routing and `--account` |
| `accounts` | providers, the two Gmail doors and their costs, app passwords, re-auth |
| `providers` | declaration files, merge order, readiness, `provider add|edit|remove`, hosts and OAuth keys |
| `vault` | `vault init`, the password rules, lockout, `--password-stdin` and `--password-file`, the system credential store and its trade, what is stored |
| `mail` | folders, threads, reply states, attachments, truncation |
| `jobs` | states, retries, failures, manual create versus batch |
| `status` | health lines, doctor checks, logs, where the log lives |
| `backup` | what a bundle contains, restore steps, what is replaced |
| `config` | settings, sources, validation, restart requirements, appearance |
| `json` | output shapes, list totals, error objects, exit codes, no prompts |
| `glossary` | every domain word, including `reply_state`, `attempt`, `batch`, `job`, `thread` |

## Appendix B: glyph set

| Purpose | Nerd | ASCII |
|---|---|---|
| selected row | `\uf054` | `>` |
| unselected row | ` ` | ` ` |
| success, `connected`, `sent` | `\uf00c` | `[ok]` |
| failure, `not signed in` | `\uf00d` | `[fail]` |
| warning | `\uf071` | `!` |
| folder | `\uf07b` | `[dir]` |
| file | `\uf15b` | `[file]` |
| mail | `\uf0e0` | `@` |
| clock | `\uf017` | `[time]` |
| lock | `\uf023` | `[lock]` |
| key | `\uf084` | `[key]` |
| arrow | `\uf061` | `->` |

Rules: a glyph is never the only label. Success is green, failure red. A line that is still
working prints plain text with a trailing ellipsis, `checking imap.gmail.com:993 ... 1.2s`, and
carries no glyph. In ASCII the words `connected` and `not signed in` are the part that carries
meaning, so a stripped terminal and a screenshot still read the same. Width is computed on the
rendered string, not the glyph code point, so alignment holds.

## Appendix C: glossary to print

| Word | Meaning in downcroc |
|---|---|
| account | one mailbox downcroc sends from and reads |
| attempt | one OAuth connect flow, alive independently of the CLI |
| batch | all jobs created from one submitted campaign |
| job | one email to one recipient; retries and fails alone |
| message | an actual email, sent or received |
| thread | a conversation linked by Message-ID headers |
| watcher | a live IMAP connection ingesting new mail |
| reply | a received message attributed to a job |
| reply state | confirmed (headers prove it), likely (subject and sender match), late (after the window), bounce (delivery failure) |
| vault | the encrypted file holding credentials |
| credential | the stored secret for an account; `signed in` in the UI |
| allowance | how many sends remain today for an account |
| in flight | a job currently being sent |
| suppression | skipping a recipient because they already replied |
| campaign | the input document: messages, routing, options, follow-ups |
| draft | a campaign written by `downcroc send` for one message or a composed set |
| provider | a mailbox service declaration: hosts, ports, TLS, auth kind |
| declaration | one `[providers.<id>]` table, shipped or written by the user |
| door | one sign-in method a provider offers, app password or OAuth client |
| throttle | a deliberate delay after repeated vault password failures |
| credential store | the operating system vault for secrets: Secret Service on Linux, Credential Manager on Windows |
| keyring on | the master password is kept in the credential store, so only the computer login is typed |

## Appendix D: issue to phase map

| Phase | Issues |
|---|---|
| A | D1, D4, D8, D12, D16 (interactive half), D19, D30, D36, D37, D38, D39, D50, D51, D53, D54, D59, D70, D72, D75 |
| B | D16 (discovery half), D17, D18, D28, D40, D41, D42, D43, D52 |
| C | D2, D3, D5, D6, D7, D9, D10, D11, D13, D14, D15, D20, D21, D22, D23, D24, D25, D26, D29, D31, D32, D33, D35, D48, D49, D55, D56, D57, D58, D60, D61, D62, D63, D64, D65, D66, D67, D68, D69, D71 |
| P | D27 |
| 04 | D34 |
| deferred | D44, D45, D46, D47, D73, D74 |

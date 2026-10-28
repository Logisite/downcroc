# downcroc CLI usability report

Version tested: `downcroc 1.0.0rc1`
Date: 2026-10-27
Method: black-box only. No source files were read. Every command was run through the installed CLI against a real daemon, real SQLite storage, and real logs in an isolated home directory (`/tmp/opencode/downcroc-ux`). The real user configuration, vault, database, and logs were not touched.

## Verdict

The CLI is technically solid underneath and the error vocabulary is good, but it is not usable without reading the source or the design docs. The core promise, "add an account, submit a batch, send mail", cannot be completed through the CLI alone: the only declared providers cannot be configured, batch routing cannot be directed to an account, and the intake format has to be guessed one validation error at a time.

The best parts are `config schema`, `config set`, `--json` output, duplicate-recipient detection, and the daemon-down hint. The worst parts are first-run vault creation, the account/provider dead end, and silent success on invalid filters.

## Severity summary

| Severity | Count | Meaning |
| --- | --- | --- |
| Blocking | 4 | Prevents completing the primary workflow |
| High | 11 | Breaks automation, trust, or discoverability |
| Medium | 14 | Confusing, inconsistent, or unsafe defaults |
| Low | 8 | Cosmetic or minor friction |

## Blocking

### B1. No account can be connected out of the box

The only providers are `generic`, `gmail`, and `microsoft`. None can be connected through the CLI.

```
$ downcroc account add --provider generic --address demo@example.com
created acct_010e69e9ae1111d4 (pending)

$ printf 'app-password\n' | downcroc account connect --password-stdin acct_010e69e9ae1111d4
error: provider_not_configured: the provider has no imap host
```

`account providers --json` describes `generic` as:

```
"notes": "Template only. Declare a provider with real hosts in providers.toml or providers.d."
```

The same for OAuth:

```
$ downcroc account attempt --wait --timeout 1 acct_6afd4745c9ab4172
error: oauth_not_configured: the provider has no oauth client id
```

Why it hurts: the first real task, connecting a mailbox, fails with no in-CLI remedy. The workaround exists only in prose inside a JSON note.

Suggested fix: add `provider add/edit/list` commands, or accept `--imap-host`, `--imap-port`, `--smtp-host`, `--smtp-port`, and `--oauth-client-id` on `account add`. At minimum, the error must say where to put the missing value and print the config path.

### B2. The CLI cannot configure providers or OAuth

`config schema` contains no provider or OAuth client fields. Provider declarations are a separate TOML file, and the CLI never names it outside `--json` notes. `config set` cannot reach it.

Suggested fix: expose the provider file through the CLI, or document it in `account add --help` and in the error hint.

### B3. Batch routing cannot be directed to an account

Per-message `account` is accepted and then ignored:

```
$ downcroc batch preview b1.json
recipient      subject  account
a@example.com  S        -
ignored: account
```

Top-level routing is rejected:

```
$ downcroc batch preview b2.json
error: batch_invalid: 1 problem(s) in the source, first: unknown field account

$ downcroc batch preview b3.json
error: batch_invalid: 1 problem(s) in the source, first: unknown field routing
```

Preview exits 0 with `account -`, then submit fails later:

```
$ downcroc batch submit b8.json
error: account_unavailable: no connected account matches the routing policy
```

Why it hurts: there is no way to pin a batch to a specific sender, and the failure arrives only after the user believes preview passed. The `ignored: account` line appears after the table, where it is easy to miss.

Suggested fix: make `account` a real per-message field, add `--account` to `batch preview` and `batch submit`, and fail preview when no account would be selected. Report ignored fields before the table, or make them hard errors.

### B4. There are no interactive flows

There is no setup wizard, no guided account creation, and no confirmation prompt for destructive actions. `account delete` on a TTY still refuses flatly:

```
$ downcroc account delete acct_3415c9f5e287afb6
error: refusing to delete without --yes
```

It never asks "delete demo@example.com? [y/N]". `restore` has no confirmation or dry run at all.

Suggested fix: add a first-run `setup` or `doctor`, prompt on destructive actions when stdin is a TTY, and keep `--yes` for scripts.

## High

### H1. Non-TTY vault unlock dumps a Python traceback

```
$ downcroc vault unlock < /dev/null
/usr/lib/python3.14/getpass.py:99: GetPassWarning: Can not control echo on the terminal.
Warning: Password input may be echoed.
Vault password: Traceback (most recent call last):
  ...
termios.error: (25, 'Inappropriate ioctl for device')
  ...
EOFError
```

Why it hurts: cron, CI, containers, and any non-interactive runner get Python internals instead of "no terminal available, use --password-stdin". It also exposes file paths and the Python version.

Suggested fix: detect `not sys.stdin.isatty()` before calling getpass and print a single actionable error.

### H2. First unlock silently creates the vault

There is no `vault init`. On a fresh install, `vault unlock` creates the vault with whatever password is supplied, with one entry and no confirmation.

```
$ downcroc vault unlock
Vault password:
state unlocked
```

The log records `vault.created`, but the CLI says nothing. A typo becomes the permanent master password, and there is no `vault passwd` to change it.

Suggested fix: add `vault init` with a repeat prompt and require it before `unlock`. Add `vault passwd`.

### H3. Lockout is invisible to the user and to scripts

After five wrong passwords:

```
$ downcroc vault status
state          locked
attempts_left  0
retry_after_s  0.0

$ printf 'wrong-6\n' | downcroc vault unlock --password-stdin
error: vault_bad_password: the master password is not correct
```

The sixth attempt is actually delayed (about 3.3 s versus a 1.4 s baseline), but the error is unchanged and `retry_after_s` still reports `0.0`. A user cannot tell they are being throttled. A script cannot tell either.

Suggested fix: return a distinct `vault_throttled` error with the wait time, and reflect the delay in `vault status` before the next attempt.

### H4. Unlocking an unlocked vault is an error

```
$ printf 'secret-pass\n' | downcroc vault unlock --password-stdin
error: vault_already_unlocked: the vault is already unlocked
```

Why it hurts: every script must check state first, and a retry after a timeout can fail even though the vault is in the desired state.

Suggested fix: make unlock idempotent, or add `--if-locked`.

### H5. `service status` exits 0 when the daemon is stopped or stale

```
$ downcroc service status
state  stopped
[exit=0]

$ downcroc service status
state  stale
pid    22321
port   8765
[exit=0]
```

Why it hurts: health checks and scripts cannot detect a dead daemon from the exit code. The user only discovers it on the next command.

Suggested fix: exit non-zero for `stopped` and `stale`, and print the start hint then.

### H6. The intake schema has to be guessed

Building one valid JSON file took six attempts:

```
unknown field email
messages must be an array
to must be an object
unknown field address
a message needs text or html
subject is required
```

Every error reports only the first problem of N and never lists allowed fields:

```
error: batch_invalid: 10 problem(s) in the source, first: unknown field email
```

The valid shape is:

```json
{"messages":[{"to":{"email":"a@example.com","name":"A"},"subject":"S","text":"T"}]}
```

Suggested fix: add `downcroc batch example --format json` and `--format csv`, show a complete example in `batch submit --help`, list allowed fields on unknown-field errors, and print all problems rather than only the first.

### H7. CSV templates are named but cannot be listed

```
$ downcroc batch preview demo.csv
error: batch_invalid: a CSV needs a template
  template: required for CSV

$ downcroc batch preview demo.csv --template /tmp/opencode/ux/template.json
error: input_unreadable: invalid template name '/tmp/opencode/ux/template.json'
```

There is no command to list, show, or validate templates, and no documentation of the expected template fields. Guessing names is the only path.

Suggested fix: add `batch template list|show|validate`, accept a path as well as a name, and print an example template in help.

### H8. Preview can hang on template options

Three invocations hit a 20 s timeout (exit 124):

- `batch preview c1.csv` with no `--template`
- `batch preview c1.csv --template simple`
- `batch preview b6.json --key mykey --template tpl`

The same CSV-without-template call failed instantly earlier in the session. This was not reproduced after the environment restart and needs a clean re-test before being treated as confirmed.

Suggested fix: reject `--template` for JSON sources, and put a short client timeout around template resolution so a bad name cannot hang the CLI.

### H9. `job create` accepts a pending account that batches refuse

The account has no credential and status `pending`:

```
$ downcroc account list
acct_010e69e9ae1111d4  demo@example.com  generic  pending  no  yes

$ downcroc job create --account acct_010e69e9ae1111d4 --to a@example.com --subject S --text T
created job_5b4e084669f8b6bb (queued)
```

The same account cannot be used for a batch (`account_unavailable`). The job will sit queued and later fail. There is no warning at creation time.

Suggested fix: validate account state in `job create`, or print a warning such as "account is not connected; job will not send until it is".

### H10. Invalid filters silently return empty results

```
$ downcroc job list --state nonsense
id  recipient  state  attempts  subject  sent

$ downcroc mail list --since nonsense
date  from  subject  reply  attachments  id

$ downcroc mail list --folder NOPE
date  from  subject  reply  attachments  id

$ downcroc stats summary --account acct_missing
sent 0
failed 0
```

All exit 0. A typo looks identical to "no data".

Suggested fix: validate enums and dates client-side, and return `not_found` for an unknown account. Use argparse choices so `--help` lists the values.

### H11. `logs --limit 0` and `--limit -1` dump the entire log

```
$ downcroc logs --limit 0
03:32:42.296  info  config.reloaded ...
... every line since the first run ...
```

Both values are accepted and interpreted as "no limit". A negative or zero limit should be rejected, not silently expanded.

### H12. Missing text file leaks a raw Python errno

```
$ downcroc job create ... --text-file /tmp/opencode/ux/nope.txt
error: [Errno 2] No such file or directory: '/tmp/opencode/ux/nope.txt'
```

Every other error uses `error: code: message` with structured fields. This one exposes the Python exception text.

Suggested fix: wrap file reads and return `input_unreadable` with the path.

### H13. Unlock prints an unrelated credential table

When at least one account exists, `vault unlock` prints a second table with no heading or explanation:

```
state          unlocked
path           /tmp/opencode/downcroc-ux/.local/share/downcr...
unlocked_at    2026-10-27T03:32:20.413Z
attempts_left  5
retry_after_s  0.0
account                credential
---------------------  ----------
acct_010e69e9ae1111d4  no
```

The same stray table appears in `account list`, duplicating the account ID column. The header `account` is a section name, not a field, and it reads as a bug.

Why it hurts: the most security-sensitive command in the product ends with unexplained output about credentials.

Suggested fix: remove the extra table from unlock and from `account list`, or print a labelled section such as `credentials:`.

## Medium

### M1. Pending accounts report the watcher as enabled

```
acct_010e69e9ae1111d4  demo@example.com  generic  pending  no  yes
```

`watcher_enabled` is true before any credential exists. It is misleading and makes `account watch --on` look like it did something.

Suggested fix: default watcher off until the account is connected.

### M2. `account show` splits into two unaligned blocks

```
last_error        -
last_uid      0
uidvalidity   0
last_sync_at  -
failures      0
allowance     200
window        0..24
in_flight     2
```

The top section is aligned; the sync and quota sections are not, and there is no blank line or label to separate them.

Suggested fix: render labelled `sync` and `quota` sections with consistent column widths.

### M3. Provider table is misleading

```
id         auth          ...  oauth
gmail      oauth2             no
microsoft  oauth2             no
```

The column means "OAuth client configured", but it reads as "this provider does not use OAuth". `--json` calls it `oauth_configured`, which is correct. The table also hides the `notes` field that explains how to fix it.

Suggested fix: rename to `oauth_ready`, and print the notes or a `--notes` option.

### M4. `account attempt` gives no next step

```
$ downcroc account attempt --wait --timeout 1 acct_...
error: provider_auth_mismatch: this provider does not use oauth
```

There is no hint to use `account connect` for app-password providers.

### M5. Gmail password connect checks the wrong thing first

```
$ downcroc account connect --password-stdin acct_gmail
a password is required
```

For an OAuth provider, the useful error is "this provider uses OAuth; run account attempt", not a password complaint.

### M6. `--password-stdin` silently ignores extra lines

Input `secret-pass\nignored-second-line\n` unlocks successfully using only the first line. A pasted multi-line value can appear to work while silently truncating. Read one line and reject extra non-empty input, or document first-line-only behavior.

### M7. `backup` before first boot is unhelpful

```
$ downcroc backup /tmp/opencode/ux/cold-backup.zip
backup failed: database does not exist
```

No `error:` prefix, no hint, no suggestion to run `service start` first.

### M8. `restore` logs the same warning twice and drops the path

```
$ downcroc restore /tmp/opencode/ux/does-not-exist.zip
13:40:04.954  warning  backup.verify_failed  file=does-not-exist.zip
13:40:05.001  warning  backup.verify_failed  file=does-not-exist.zip
13:40:05.002  warning  restore.refused  ... reason=bundle cannot be read
restore refused: bundle cannot be read
```

The path is truncated to the basename, so the log cannot tell you which file failed. The same event fires twice.

### M9. No `--json` on delete, backup, or restore

`account delete`, `backup`, and `restore` have no machine-readable output. Error output is never JSON, even when other commands support `--json`, so a JSON-first script cannot handle failures.

### M10. No `doctor`, examples, or completion

`--help` has no examples anywhere. There is no `doctor` for first-run state, no `batch example`, and no `completion bash|zsh|fish`. This is the root cause of most of the guessing above.

### M11. Vault path is truncated in table output

```
path  /tmp/opencode/downcroc-ux/.local/share/downcr...
```

The full path requires `--json`. Truncate only on a narrow TTY, or add `--path`.

### M12. `vault status` reports lockout fields when unlocked

```
state          unlocked
attempts_left  5
retry_after_s  0.0
```

These read as warnings even when nothing is wrong. Show them only when locked or throttled.

### M13. `logs` with no daemon is silent success

```
$ downcroc logs
[exit=0]
```

A missing daemon looks like an empty log. Emit the daemon-down hint, or a note that the log file does not exist yet.

### M14. `service start` is slow and silent

Measured `service start` took 15.6 s before returning. Output is a single line after the wait:

```
started on http://127.0.0.1:8765 (pid 27941)
```

No progress, no "waiting for health", no timeout indication. On a slow disk the user cannot tell whether it is working.

### M15. API wording leaks into CLI errors

```
$ downcroc mail list --limit 0
error: invalid_request: the request body is not valid
  limit: Input should be greater than or equal to 1
```

`mail list` is a GET-style query, but the message talks about a request body. Pydantic phrasing ("Input should be...") is also exposed. Validate client-side.

### M16. Argparse uses a different error style and exit code

Missing required flags produce the argparse usage block and exit `2`, while every domain error is `error: code: message` and exits `1`. Scripts need two error parsers.

### M17. Bare `downcroc` is not help or onboarding

With no subcommand, it prints only:

```
state  stopped
start it with: downcroc service start
```

There is no command list, no next step after starting, and no mention of the vault.

## Low

### L1. Successful mutations give no next step

`account add` prints `created acct_... (pending)` and stops. It could print `next: downcroc account connect acct_...`.

### L2. `account watch` requires an explicit flag

`account watch <id>` errors with "one of --on --off is required". A TTY toggle or default-on would be friendlier.

### L3. Batch idempotency is not exposed

`batch preview` accepts `--key`, but `batch submit --help` does not. A retried submit has no documented way to reuse the previewed key, so duplicate batches are likely. Not exercised end to end because submit could not succeed.

### L4. `logs --since nonsense` has no format hint

```
cannot read --since nonsense
```

No `error:` prefix, and no list of accepted formats, even though `logs --help` documents them.

### L5. Unknown folders and states are silently empty

Covered under H10. Listed here because it also affects discoverability: `--help` should show the allowed values.

### L6. `stats summary --account` accepts unknown accounts

Covered under H10. It returns zeros instead of `account_not_found`, unlike every other command.

### L7. `openapi -o` creates missing directories silently

Running as root, `-o /nonexistent/dir/openapi.json` printed `wrote ...` and exited 0. If directory creation is intended, it is undocumented; if not, this should fail on a read-only parent.

### L8. Vault password has no file or environment option

Only interactive getpass and `--password-stdin` exist. That is the right default for secrets, but a `--password-file` option would cover systemd and container secret mounts without shell pipelines.

## What works well

- `config schema` is the best surface in the CLI. Every field has type, default, range, and description, and it is complete.
- `config set` validation is clear and specific: `field: sending.daily_allowance`, `reason: Input should be greater than or equal to 1`. Changes hot reload and are logged as `config.reloaded`.
- `--json` output on read commands is clean, stable, and includes useful nulls.
- Duplicate recipient detection is precise: `a@example.com appears in both m1 and m2`.
- Daemon-down errors carry the right hint: `start it with: downcroc service start`.
- The password is hidden on a real TTY. An earlier apparent echo in this test was caused by the pseudo-terminal replaying input, not by the CLI. This is cleared as a false positive.
- Unknown IDs produce consistent, specific errors: `account_not_found`, `job_not_found`, `batch_not_found`, `message_not_found`, `thread_not_found`, `attachment_not_found`.
- `stats` date validation is good: `from must not be after to`, with a format hint for bad dates.

## Untested or blocked

These could not be exercised end to end because the CLI cannot produce a connected account without a real mailbox or OAuth client. They must not be reported as passing.

- `batch show`, `batch approve`, `batch cancel`, `batch followup`, `batch suppression`
- `job send` and the dispatcher send path
- `failed show`, `failed retry` on a real failure
- `mail list`, `mail show`, `mail threads`, `mail thread`, `mail attachment` with stored mail
- Mail sync, watcher behaviour, and reply/thread detection
- Send quotas, jitter, windows, retries, and bounce handling
- Backup and restore with a populated database
- The CSV named-template format and its rendering

Additional caveats:

- The daemon used for the first half of the session was cancelled by an environment restart, not by the CLI.
- The template-related hangs in H8 need a clean re-test.
- `openapi -o /nonexistent/...` succeeded because the test ran as root.

## Recommended fix order

1. Add `vault init`, make unlock idempotent, and replace the non-TTY traceback with one actionable error. (H1, H2, H4)
2. Make an account connectable: provider configuration in the CLI, with actionable errors pointing at the exact file and key. (B1, B2)
3. Add `batch example`, `batch template list`, allowed-field lists, and all-problems reporting. (H6, H7)
4. Add account selection to preview and submit, and fail preview when routing is empty. (B3)
5. Validate enums, dates, limits, and unknown accounts client-side, and stop returning empty success. (H10, H11, M15, M16)
6. Make `service status` exit non-zero when not running, and add `service restart`. (H5)
7. Remove the stray credential table and fix pending-account watcher defaults. (H13, M1)
8. Add `doctor` and next-step hints to every state-changing command. (B4, M10)
9. Add `--json` to delete, backup, and restore, plus structured errors and stable exit codes. (M9, M16)
10. Add `--account` warnings in `job create` and a provider-state preflight before queueing. (H9)

## Reproduction environment

```sh
export HOME=/tmp/opencode/downcroc-ux
export XDG_CONFIG_HOME= XDG_DATA_HOME= XDG_STATE_HOME=
uv run downcroc service start
printf 'secret-pass\n' | uv run downcroc vault unlock --password-stdin
```

The isolated home was used for every command. The real user home was never touched.

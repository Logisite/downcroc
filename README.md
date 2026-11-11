<pre>
█▀▀▄ █▀▀█ █   █ █▀▀▄ █▀▀▀ █▀▀▄ █▀▀█ █▀▀▀
█  █ █  █ █   █ █  █ █    █  █ █  █ █
█  █ █  █ █ █ █ █  █ █    █    █  █ █
█  █ █  █ █▄█▄█ █  █ █    █    █  █ █
▀▀▀▀ ▀▀▀▀ ▀   ▀ ▀  ▀ ▀▀▀▀ ▀    ▀▀▀▀ ▀▀▀▀
</pre>

![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)
![Linux and Windows](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-2ea44f)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Local first](https://img.shields.io/badge/data-stays%20local-6f42c1)

**Always-on local mail daemon for personalised mail merged from your own Gmail or IMAP accounts.**

Downcroc sends batches, tracks replies and bounces, keeps statistics on your machine, and never
depends on a hosted control plane.

---

## Why downcroc

Most mail merge tools want your mailbox, your recipient list, and your sending history in their
cloud. Downcroc keeps all three on your computer. It runs as a local user service, exposes a
loopback-only HTTP API, and encrypts every credential in a vault that only you can unlock.

| | |
|---|---|
| **Local first** | Config, database, content, logs, and credentials stay on your machine. |
| **Your accounts** | Gmail OAuth, Microsoft OAuth, or any IMAP/SMTP mailbox with an app password. |
| **Batch sending** | Campaign files, CSV plus templates, preview, approval, scheduling, holds, and quotas. |
| **Reply aware** | Threads, replies, bounces, suppression, and follow-ups are stored locally. |
| **Observable** | Structured JSONL logs, live events, statistics, doctor checks, and capacity estimates. |
| **Recoverable** | Encrypted vault, backup and restore, and a service that survives logout and restart. |

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Sending](#sending)
- [Follow-ups](#follow-ups)
- [Monitoring and control](#monitoring-and-control)
- [Configuration](#configuration)
- [Security](#security)
- [How it works](#how-it-works)
- [Development](#development)
- [Release notes](#release-notes)
- [License](#license)

## Requirements

- Python 3.14 or newer for the wheel
- Linux or Windows
- A Gmail OAuth client for the recommended Gmail route, or an app password for IMAP/SMTP

macOS is not part of the release 1 support scope.

## Install

Linux and other POSIX shells:

```sh
curl -fsSL https://raw.githubusercontent.com/Logisite/downcroc/master/scripts/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/Logisite/downcroc/master/scripts/install.ps1 | iex
```

For an offline install, pass a local wheel:

```sh
scripts/install.sh --wheel downcroc-1.3.1-py3-none-any.whl
```

```powershell
.\scripts\install.ps1 -Wheel .\downcroc-1.3.1-py3-none-any.whl
```

## Update and remove

```sh
downcroc update --check
downcroc update
downcroc update --version 1.3.1 --force
downcroc uninstall
downcroc uninstall --purge
```

`update` replaces the installed wheel and restarts a running service. It keeps config, data, and
state.

`uninstall` removes the launcher and installed environment but keeps config, data, and state.
`--purge` also removes them.

The installer also accepts a version:

```sh
scripts/install.sh --version 1.3.1
```

```powershell
.\scripts\install.ps1 -Version 1.3.1
```

## Quick start

```sh
downcroc init
downcroc account add --provider gmail --address you@example.com
downcroc account connect ACCOUNT_ID
downcroc doctor
```

Connect Gmail with OAuth when possible. OAuth gives the mailbox an SMTP seat and a Gmail API
lane. App-password accounts work over IMAP/SMTP only, with one serial send seat and a bounded
send rate.

Start the daemon as a user service:

```sh
downcroc service install
downcroc service start
downcroc service status
```

Or run it in the foreground:

```sh
downcroc serve
```

The daemon binds `127.0.0.1:8765` by default and starts locked. Unlock it through
`downcroc vault unlock`.

## Documentation

```sh
downcroc docs
downcroc docs smtp-seats
downcroc docs --list
downcroc docs --search seat
downcroc docs --open
```

`downcroc docs` opens the terminal browser. The same Markdown book is packaged in the wheel.
`--open` opens the current page file in your browser.

## Sending

```sh
downcroc batch validate campaign.json
downcroc batch preview campaign.json
downcroc batch submit campaign.json --approve all
downcroc batch list
downcroc job list
downcroc failed list
```

The interactive interface covers the same workflow:

```sh
downcroc
```

Useful send controls:

```sh
downcroc batch submit campaign.json --dry-run
downcroc batch submit campaign.json --key m1
downcroc batch submit campaign.json --allow-overlap
downcroc job create --account ACCOUNT_ID --to person@example.com --subject Hello --text Body
downcroc job send JOB_ID
```

## Follow-ups

Follow-ups can be declared at submit time, sent immediately from a payload, or declared
retroactively against an existing campaign batch. Parent snapshots stay immutable. Retroactive
declarations are database rows, so remove, retire, and status work without rewriting the campaign
file.

```sh
downcroc batch followups declare PARENT_BATCH fu1.json --step fu1
downcroc batch followups status PARENT_BATCH
downcroc batch followups remove PARENT_BATCH --step fu1
downcroc batch followups retire PARENT_BATCH --step fu1
```

Every child is created as a reply to the message that actually reached the recipient. Threading
headers and sender identity are derived from the parent chain, not guessed.

## Monitoring and control

```sh
downcroc status
downcroc doctor
downcroc doctor capacity
downcroc doctor inbound
downcroc stats summary --since 7d
downcroc mail list
downcroc logs --follow
downcroc logs --addresses --event account. --since 15m
downcroc service pause --for 1h --reason maintenance
downcroc service resume
downcroc service stop
```

Pause is reversible. In-flight attempts settle, inbound mail keeps running, and queued work
resumes when the hold is released.

The interactive credential preflight shows a compact status strip after unlock:

```text
   ╒── credential check ──────────────────────────────────────────────────╕
   ║  [ok] 11 ready   ! 1 reconnect   . 0 unavailable   [time] 1m ago      ║
   ╘──────────────────────────────────────────────────────────────────────╛
```

Green means every checked account is ready. Yellow means at least one needs reconnect. Red means
a credential or provider check is unavailable.

## Configuration

```sh
downcroc config show
downcroc config schema
downcroc config set sending.jitter_min 2
downcroc account policy show ACCOUNT_ID
```

Configuration is read live. Account policy overrides are nullable, so an account inherits global
`[sending]` values unless it has an explicit override.

## Security

- Credentials live in the encrypted vault, not in SQLite.
- The API binds to loopback and requires the per-run bearer token.
- Secrets are not written to logs, events, API responses, or backups in plaintext.
- Credential, token, and password fields are scrubbed at the logging boundary.
- The daemon should run as your user, not as root.

## How it works

```text
 campaign file or CSV
          |
          v
   parse -> validate -> snapshot -> route -> jobs
                                           |
                                           v
                              dispatcher: window, quota, holds,
                              lease, seat, send, attempt, reconcile
                                           |
                                           v
                           local SQLite + content store + JSONL log
```

- The API and CLI talk over loopback HTTP. The daemon owns all state.
- IMAP watchers never touch SQLite. They hand work to the ingester.
- The SMTP seat is a transport reservation, not an account status.
- Provider responses, not numeric status codes alone, decide retry, quota, and reauth.
- Batch, job, and pending estimates carry `as_of` and `basis` and are recomputed on every read.

## Development

From a checkout:

```sh
uv sync
uv run downcroc --version
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
```

Build a wheel or standalone binary:

```sh
uv build
uv sync --group build
uv run python scripts/build_binary.py pyinstaller
```

Design notes and implementation tickets live in `plan/` and `.scratch/`.

## Project

- [Documentation book schema](plan/15-docs-book.md)
- [Page frontmatter schema](docs/schema.json)
- [Changelog](CHANGELOG.md)
- [Release notes](release-notes/)
- [Security policy](SECURITY.md)
- [Design notes](plan/)
- [License](LICENSE)

## Release notes

See [`release-notes/`](release-notes/) for the full history. The current release is
[`1.3.1`](release-notes/v1.3.1.md).

## License

Apache License 2.0. See `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`.

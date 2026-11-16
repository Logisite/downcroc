<pre>
█▀▀▄ █▀▀█ █   █ █▀▀▄ █▀▀▀ █▀▀▄ █▀▀█ █▀▀▀
█  █ █  █ █   █ █  █ █    █  █ █  █ █
█  █ █  █ █ █ █ █  █ █    █    █  █ █
█  █ █  █ █▄█▄█ █  █ █    █    █  █ █
▀▀▀▀ ▀▀▀▀ ▀   ▀ ▀  ▀ ▀▀▀▀ ▀    ▀▀▀▀ ▀▀▀▀
</pre>

![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)
![Platform: Linux | Windows](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-2ea44f)
![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
![Local-first](https://img.shields.io/badge/data-stays%20local-6f42c1)

**Downcroc** is a local-first mail daemon for sending personalized mail from your own Gmail or IMAP/SMTP accounts. It runs on your machine, stores data locally, and operates without a hosted control plane.

## Overview

Downcroc manages campaign and batch sending, delivery tracking, replies and bounces, follow-ups, and operational visibility from a local daemon and CLI. Credentials are stored in an encrypted local vault, and the daemon exposes a loopback-only HTTP API.

## Key capabilities

- **Local-first operation** — configuration, database, message content, logs, and credentials remain on your machine.
- **Bring your own mailboxes** — connect Gmail (OAuth) or IMAP/SMTP accounts (including app-password flows where applicable).
- **Batch and campaign sending** — validate, preview, submit, approve, schedule, pause/hold, and monitor sends with policy and quota controls.
- **Reply-aware workflows** — track threads, replies, bounces, suppression, and follow-ups locally.
- **Operational visibility** — structured JSONL logs, service/doctor/status views, statistics, and capacity/queue inspection.
- **Recovery and portability** — encrypted vault, backup/restore workflows, and user-service operation.

## Requirements

- Python 3.14 or newer
- Linux or Windows
- A supported mailbox/account configuration (for Gmail, OAuth is recommended)

> macOS is out of scope for the current release support target.

## Installation

### Linux / POSIX shells

```sh
curl -fsSL https://raw.githubusercontent.com/Logisite/downcroc/master/scripts/install.sh | sh
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/Logisite/downcroc/master/scripts/install.ps1 | iex
```

### Offline install

```sh
scripts/install.sh --wheel downcroc-<version>-py3-none-any.whl
```

```powershell
.\scripts\install.ps1 -Wheel .\downcroc-<version>-py3-none-any.whl
```

### Update and uninstall

```sh
downcroc update --check
downcroc update
downcroc uninstall          # removes launcher/environment; keeps config/data/state
downcroc uninstall --purge  # also removes config/data/state
```

## Quick start

```sh
downcroc init
downcroc account add --provider gmail --address you@example.com
downcroc account connect <account_id>
downcroc doctor
```

Run as a user service:

```sh
downcroc service install
downcroc service start
downcroc service status
```

Or run in the foreground:

```sh
downcroc serve
```

By default the daemon binds to `127.0.0.1:8765` and starts with the vault locked. Unlock when needed:

```sh
downcroc vault unlock
```

## Sending and batch workflows

```sh
downcroc batch validate campaign.json
downcroc batch preview campaign.json
downcroc batch submit campaign.json --approve all
downcroc batch list
downcroc job list
downcroc failed list
```

Interactive mode is available via:

```sh
downcroc
```

## Follow-ups

Downcroc supports follow-up steps defined in campaigns and retroactive follow-up declarations on existing campaign batches (including status, update, remove, and retire workflows), with threaded replies derived from the parent message chain.

```sh
downcroc batch followups declare <parent_batch_id> fu1.json --step fu1
downcroc batch followups status <parent_batch_id>
downcroc batch followups remove <parent_batch_id> --step fu1
downcroc batch followups retire <parent_batch_id> --step fu1
```

## Monitoring and control

```sh
downcroc status
downcroc doctor
downcroc service pause --for 1h --reason maintenance
downcroc service resume
downcroc logs --follow
downcroc stats summary --since 7d
downcroc mail list
```

## Documentation

Downcroc includes a packaged, offline documentation book (Part I: The Craft, Part II: The Commands, Part III: The Machine).

```sh
downcroc docs                         # open the terminal docs browser
downcroc docs --list                  # list pages
downcroc docs --search seats          # search the book
downcroc docs 31-seats-and-threads    # read a topic
downcroc docs --open                  # open the current page in your browser
downcroc help vault                   # short terminal help
```

## Configuration

```sh
downcroc config show
downcroc config schema
downcroc config set sending.jitter_min 2
downcroc account policy show <account_id>
```

Configuration is read at runtime; account-level policy overrides take precedence where explicitly set.

## Security model

- Credentials are stored in the encrypted local vault, not in the application database.
- The daemon API binds to loopback and requires a per-run bearer token (with limited public endpoints as designed).
- Secrets must not be written to logs, events, API responses, or backup bundles.
- Sensitive fields are scrubbed at logging boundaries.
- Run the daemon as a regular user (not root).

## Architecture (high level)

```text
 campaign file / CSV / CLI input
                 |
                 v
        parse -> validate -> snapshot -> route -> jobs
                                                 |
                                                 v
                                dispatcher (window, quota, holds,
                                lease, transport, attempts, reconcile)
                                                 |
                                                 v
                      local SQLite + content store + structured JSONL logs
```

The CLI communicates with the daemon over loopback HTTP. The daemon owns state and orchestrates sending, inbound processing, and follow-up planning.

## Development

From a source checkout:

```sh
uv sync
uv run downcroc --version
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
```

Build artifacts:

```sh
uv build
uv sync --group build
uv run python scripts/build_binary.py pyinstaller
```

## Project resources

- [Changelog](CHANGELOG.md)
- [Release notes](release-notes/)
- [Security policy](SECURITY.md)
- [Design notes](plan/)
- [License](LICENSE)
- [Documentation book plan](plan/15-docs-book.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

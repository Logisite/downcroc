<pre>
█▀▀▄ █▀▀█ █   █ █▀▀▄ █▀▀▀ █▀▀▄ █▀▀█ █▀▀▀
█  █ █  █ █   █ █  █ █    █  █ █  █ █
█  █ █  █ █ █ █ █  █ █    █    █  █ █
█  █ █  █ █▄█▄█ █  █ █    █    █  █ █
▀▀▀▀ ▀▀▀▀ ▀   ▀ ▀  ▀ ▀▀▀▀ ▀    ▀▀▀▀ ▀▀▀▀
</pre>

**Always-on local mail daemon · Linux and Windows**

Downcroc is an always-on local mail daemon for personalised mail merged from
your own Gmail or IMAP accounts. It sends batches, tracks replies and bounces,
keeps statistics on your machine, and never depends on a hosted control plane.

## Requirements

- Python 3.14 or newer for the wheel
- Linux or Windows
- A Gmail OAuth client for the recommended Gmail route, or an app password for
  IMAP/SMTP

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

The script downloads the matching release wheel, installs it into a user
prefix, creates the `downcroc` launcher, and prints the installed version.
The default prefix is `~/.local` on Unix and `%LOCALAPPDATA%\downcroc` on
Windows.

For an offline install, pass a local wheel:

```sh
scripts/install.sh --wheel downcroc-1.2.6.post10-py3-none-any.whl
```

```powershell
.\scripts\install.ps1 -Wheel .\downcroc-1.2.6.post10-py3-none-any.whl
```

## Update and remove

```sh
downcroc update --check
downcroc update
downcroc update --version 1.2.6.post10 --force
downcroc uninstall
downcroc uninstall --purge
```

`update` replaces the installed wheel and restarts a running service. It keeps
config, data, and state.

`uninstall` removes the launcher and installed environment but keeps config,
data, and state. `--purge` also removes them.

The installer also accepts a version:

```sh
scripts/install.sh --version 1.2.6.post10
```

```powershell
.\scripts\install.ps1 -Version 1.2.6.post10
```

## Quick start

```sh
downcroc init
downcroc account add --provider gmail --address you@example.com
downcroc account connect ACCOUNT_ID
downcroc doctor
```

Connect Gmail with OAuth when possible. OAuth gives the mailbox an SMTP seat
and a Gmail API lane. App-password accounts work over IMAP/SMTP only, with one
serial send seat and a bounded send rate.

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

## Monitoring and control

```sh
downcroc status
downcroc doctor capacity
downcroc doctor inbound
downcroc stats summary --since 7d
downcroc mail list
downcroc logs --follow
downcroc service pause --for 1h --reason maintenance
downcroc service resume
downcroc service stop
```

Pause is reversible. In-flight attempts settle, inbound mail keeps running, and
queued work resumes when the hold is released.

## Configuration

```sh
downcroc config show
downcroc config schema
downcroc config set sending.jitter_min 2
downcroc account policy show ACCOUNT_ID
```

Configuration is read live. Account policy overrides are nullable, so an
account inherits global `[sending]` values unless it has an explicit override.

## Backup

```sh
downcroc backup ~/backups/
```

Backups include the encrypted vault and its metadata. Keep the vault password
safe. The password is required to restore credentials and cannot be recovered.

## Security

- Credentials live in the encrypted vault, not in SQLite.
- The API binds to loopback and requires the per-run bearer token.
- Secrets are not written to logs, events, API responses, or backups in
  plaintext.
- The daemon should run as your user, not as root.

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

Build a wheel locally:

```sh
uv build
```

Build a standalone binary:

```sh
uv sync --group build
uv run python scripts/build_binary.py pyinstaller
```

Design notes and implementation tickets live in `plan/` and `.scratch/`.

## License

Apache License 2.0. See `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`.

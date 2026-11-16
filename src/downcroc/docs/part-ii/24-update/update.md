---
title: update
commands: [update]
flags: [--check, --pre, --force, --version, --no-restart]
concepts: []
screens: []
---

# update

`update` checks for and installs newer releases of downcroc from the project’s GitHub releases. It can report available versions, download and install a wheel, and (when appropriate) restart the daemon.

`update` operates on a managed installation (one installed via the supported install scripts/layout). Running it from a non-managed install (for example a checkout or ad-hoc environment) is refused with guidance.

## Usage

```text
downcroc update [--check] [--pre] [--force] [--version VERSION] [--no-restart]
```

## Modes

### Check for updates

```text
downcroc update --check [--pre] [--version VERSION]
```

- Fetches the release feed and reports the current and latest (or requested) version, the release URL, and release notes.
- `--pre` includes pre-release versions. `--version VERSION` targets/checks a specific release.
- With `--json`, prints the check result as JSON (current, latest, url, notes).

### Install an update

```text
downcroc update [--pre] [--force] [--version VERSION] [--no-restart]
```

- Selects the target release (latest stable by default, or latest including pre-releases with `--pre`, or a specific `--version`).
- If the target is the same as the current version, it reports “up to date” and makes no changes (unless `--force`).
- Downgrades (installing an older version than current) are refused unless `--force` is provided.
- Downloads the release wheel, verifies its checksum when a digest is provided, and installs it into the managed installation.
- Repairs the managed installation before and after installing: broken or looping interpreter links are normalized to a real Python interpreter. If the venv has no `pip` module, uv's package installer is used instead.
- If the daemon was running, it is stopped before installation and restarted afterward unless `--no-restart` is set. A restart failure after a completed install is reported as an error but the new version remains installed.

**Output**

- Default: reports current/latest (and release notes), installation progress, and the installed/previous versions and restart status.
- With `--json`: prints the result (versions, url, changed/restarted as applicable).

## Options

`--check`
: Report available/current versions without installing.

`--pre`
: Include pre-release versions.

`--force`
: Allow reinstalling the same version or downgrading.

`--version VERSION`
: Install or check a specific release version.

`--no-restart`
: Do not restart the daemon after installing (even if it was running).

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Errors and requirements

- Requires network access to reach the release feed/downloads; failures are reported (for example offline or feed/download errors).
- Must run from a managed install; otherwise the command refuses with a hint to use the supported install scripts.
- A missing wheel or checksum mismatch fails the update without installing an unverified artifact.
- If the managed install cannot be repaired (for example no supported Python interpreter is available) the update refuses with an actionable message.

## Examples

- `downcroc update --check` — check for a newer stable release.
- `downcroc update --check --pre` — include pre-releases when checking.
- `downcroc update` — install the latest stable release.
- `downcroc update --version 1.2.3` — install a specific version.
- `downcroc update --version 1.2.3 --force` — force a downgrade/reinstall to a specific version.
- `downcroc update --no-restart` — install without restarting the daemon.

## See also

- [../01-service/service.md](../01-service/service.md) — service start/stop/restart
- [../25-uninstall/uninstall.md](../25-uninstall/uninstall.md) — remove a managed install
- [../02-status/status.md](../02-status/status.md) — check running version/state

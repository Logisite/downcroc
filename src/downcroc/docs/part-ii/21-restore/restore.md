---
title: restore
commands: [restore]
flags: [--dry-run, --stop]
concepts: []
screens: []
---

# restore

`restore` verifies and restores a downcroc backup bundle. Restoring replaces the current data (accounts, batches, jobs, messages, settings, and related state) with the contents of the bundle. The previous data is preserved alongside it so recovery is possible if something goes wrong.

Because restore is destructive to the current state, it requires explicit confirmation and careful handling of a running daemon.

## Usage

```text
downcroc restore <path> [--dry-run] [--stop] [--yes]
```

- `path` is the backup bundle to restore.
- `--dry-run` verifies the bundle and shows what would be restored without making changes.
- `--stop` stops the daemon automatically if it is running (otherwise a running daemon must be stopped first).
- `--yes` skips the typed confirmation prompt (confirmation is still required in spirit; see below).

## Behavior

**Verification and dry run**

The bundle is verified before any restore. `--dry-run` prints a summary of the bundle (path, creation time, app version and schema revision, host, size/file count, counts of accounts/batches/jobs/messages/threads, and whether logs are included) and exits without changing anything. With `--json` and `--dry-run`, the summary is printed as JSON.

**Pending/resumed restore**

If a previous restore was interrupted and left a pending restore marker, `restore` resumes that pending restore instead of starting a new one.

**Daemon state**

If downcroc is running, restore refuses to proceed unless `--stop` is provided. With `--stop`, the daemon is stopped before the restore and (if it was running) started again afterward (unless running in JSON mode/output constraints prevent restart messaging; the operation attempts to restart the daemon when appropriate).

**Confirmation**

Before replacing data, restore explains that it will replace the current data at the data path and that the current data is moved beside it with a `.bak-<timestamp>` suffix. You must confirm by typing the word `restore` when prompted (unless confirmation is satisfied per `--yes`/non-interactive rules). This is a strong safeguard against accidental replacement.

**Applying the restore**

The restore swaps in the bundle’s data. On success it reports what was restored (bundle, files, counts) and the location of the preserved previous data. On refusal or failure it reports the reason; a refused bundle (for example due to version/schema incompatibility or damage) is not applied, and a failed restore keeps the previous data.

## Output

- Default: prints the bundle summary, confirmation prompts/warnings as needed, and the restore outcome (or pending/resume/refusal details).
- With `--json`: prints the bundle summary (dry run) or the restore outcome/result.

## Common flags

`--json`, `--no-input`, `--yes`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc restore backup.tar.zst --dry-run` — verify a bundle and show what it contains.
- `downcroc restore backup.tar.zst --stop` — restore a bundle, stopping and restarting the daemon if needed.
- `downcroc restore backup.tar.zst --stop --yes` — restore without the interactive confirmation prompt.

## See also

- [../20-backup/backup.md](../20-backup/backup.md) — create a backup bundle
- [../01-service/service.md](../01-service/service.md) — stop/start the daemon
- [../19-logs/logs.md](../19-logs/logs.md) — inspect logs if a restore fails
- [../part-i/03-keeping-it-running/where-is-my-stuff.md](../part-i/03-keeping-it-running/where-is-my-stuff.md) — where data lives

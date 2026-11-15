---
title: backup
commands: [backup]
flags: [--include-logs, --force]
concepts: []
screens: []
---

# backup

`backup` creates a backup bundle of downcroc’s data. The bundle captures the state needed to restore the installation (database and related data; logs can be included optionally).

## Usage

```text
downcroc backup [path] [--include-logs] [--force]
```

- `path` (optional) is where to write the backup. It can be a file path or a directory (or a path ending with a separator), in which case a timestamped backup file is created inside it. If omitted, the backup is written to a default `downcroc-backups` directory under the data location with a generated name.
- `--include-logs` includes log files in the bundle.
- `--force` allows overwriting an existing backup file at the target path.

## Behavior

- The command chooses the target path and refuses to overwrite an existing file unless `--force` is set (in an interactive session it may offer to confirm overwrite when not forced; non-interactive/declined overwrite fails with a “target exists” error).
- A database must exist to back up; if it does not, the command fails with guidance to start the daemon once first.
- If the daemon is running, the backup is created through the running daemon. If it is not running, the backup is created directly from local data.
- On success it reports the backup path, number of files, and size (bytes), and suggests verifying with `downcroc restore <path> --dry-run`.

## Output

- Default: prints progress/target and a record of the backup (path, files, bytes) and a next-step hint.
- With `--json`: prints the backup result (path, files, bytes, duration, schema revision, counts, etc. as available).

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc backup` — create a backup in the default backups directory.
- `downcroc backup /path/to/backups/` — write a timestamped backup into a directory.
- `downcroc backup /path/to/backup.tar.zst --include-logs` — create a backup including logs.
- `downcroc backup ./backup.tar.zst --force` — overwrite an existing backup file.

## See also

- [../21-restore/restore.md](../21-restore/restore.md) — verify and restore a backup bundle
- [../19-logs/logs.md](../19-logs/logs.md) — log location and reading logs
- [../part-i/03-keeping-it-running/where-is-my-stuff.md](../part-i/03-keeping-it-running/where-is-my-stuff.md) — where data lives

# 09 - Backup and restore

## What a backup is

A single file containing everything the daemon needs to be the same daemon on another machine,
or on this machine after a mistake.

``` 
downcroc-2026-10-22T09-15-00Z.dncbak
  manifest.json
  db/downcroc.db              # consistent snapshot, taken with the SQLite backup API
  content/                    # batch snapshots, rendered messages, attachments
  config/config.toml
  config/providers.toml
  config/templates/           # template directories
  vault.enc
  failed.jsonl
  logs/                       # optional, excluded by default
```

Format: a tar archive, zstd compressed, written to a temporary file and renamed on completion, so
an interrupted backup leaves a `.partial` file rather than a plausible-looking corrupt one.

`db/downcroc.db` is produced with SQLite's online backup API against a live connection. Copying
the file is not acceptable: a WAL-mode database copied mid-write can be inconsistent.

`vault.enc` is included as-is. It is already encrypted, so the bundle's sensitivity is exactly the
sensitivity of the vault password. Worth saying plainly in the UI: a backup is as safe as that
password, and no more.

## Manifest

| Field | Purpose |
|---|---|
| `bundle_format` | `1`, so the reader can refuse a format it does not know |
| `app_version` | the build that wrote it |
| `schema_revision` | the Alembic head the database was at |
| `created_at` | UTC |
| `hostname` | informational |
| `counts` | accounts, batches, jobs, messages, threads |
| `files` | path and sha256 for every entry |
| `bundle_hash` | sha256 over the sorted file hashes |
| `notes` | free text, optional |

Everything is hashed. Restore verifies the bundle hash before extracting anything, and reports
the first mismatching file by name.

## Version policy

Forward only. One direction, stated in the product rather than discovered at the worst moment.

| Bundle | Binary | Result |
|---|---|---|
| older revision | current | restore, then `alembic upgrade head` |
| same revision | current | restore |
| revision not in the local history | current | **refuse**, naming the revision |
| unknown bundle format | current | **refuse** |
| newer app version, same revision | current | restore, with a warning |

The refusal is a feature. A tool that silently half-reads a newer database corrupts the one thing
the user was trying to protect.

There is no downgrade path, and no attempt to reverse a migration. If you need the old data, keep
the old bundle.

## Creating a backup

```
POST /api/backups   { "path": "/backups/downcroc.dncbak", "include_logs": false }
```

| Step | Detail |
|---|---|
| 1 | take a read lock so no migration or prune starts mid-backup |
| 2 | snapshot the database via the backup API |
| 3 | copy content, config, templates, vault, failures |
| 4 | hash every file, write the manifest |
| 5 | stream the tar through zstd to `path.partial` |
| 6 | fsync, rename, fsync the directory |
| 7 | emit `backup.created`, release the lock |

Progress is reported through the job's status endpoint, because a bundle with 40,000 messages is
not instant.

Optional daily automatic backup to a configured path, retaining the last N. Off by default,
because writing a copy of all your mail somewhere without being asked is not a friendly default.

## Restoring

The daemon must not be running against the data it is about to replace. Two entry points, one
mechanism.

### CLI, daemon stopped

```
downcroc restore /backups/downcroc.dncbak
```

### API, daemon running

```
POST /api/restore { "path": "..." }
```

The endpoint verifies the bundle, writes a `restore.pending` marker into the state directory,
responds, and then stops the daemon. On next start, the daemon sees the marker and performs the
restore before opening the database. This keeps the destructive step out of a request that a
client could retry.

### Procedure

| Step | Detail |
|---|---|
| 1 | verify `bundle_hash` and every file hash |
| 2 | read the manifest, check `schema_revision` is in the local history, refuse if it is not |
| 3 | extract to a staging directory beside the data directory |
| 4 | run `PRAGMA integrity_check` on the staged database |
| 5 | check that every content path referenced by the database exists |
| 6 | stop watchers and the dispatcher; close the database |
| 7 | rename the live data directory to `downcroc.db.bak-<timestamp>` style siblings |
| 8 | move staging into place, preserving permissions |
| 9 | `alembic upgrade head` if the revision is behind |
| 10 | reopen, reconcile, resume |
| 11 | report counts before and after |

Steps 7 and 8 are two renames on the same filesystem, not a copy, so the window where neither
tree exists is milliseconds. If step 8 fails, step 7 is reversed and the daemon starts on the old
data with a clear error.

The previous data is never deleted by the restore. It is moved aside and named in the result, so a
mistaken restore is recoverable with `mv`.

## Verification after restore

| Check | Failure handling |
|---|---|
| Database opens and migrates | restore reported failed, old data still in place |
| Counts match the manifest | warning, listed by table |
| Sampled content hashes match | warning with the offending path |
| Vault decrypts, if a password is supplied | warning only; the password may simply not be known yet |
| Quota counters present | warning if missing, since a missing counter could mean an over-send |

The daemon comes up locked after a restore, always. The vault password is never part of the bundle.

## What is not in a bundle

| Excluded | Why |
|---|---|
| Vault password | never stored anywhere |
| Cached access tokens outside the vault | they live only in the vault |
| `service.json` | machine-specific runtime state |
| Daemon memory | nothing important lives there, by design |

## Size and time expectations

Bodies in SQLite, attachments on disk. A year of moderate use with attachments is measured in
gigabytes, most of it attachments. The backup screen shows estimated size before starting, and the
tar is streamed rather than staged, so peak disk use is roughly the bundle size plus the working
set, not double the data directory.

Pruned data is not in the bundle. If you want a historical archive, back up before retention
removes it, or raise the retention window. The product does not quietly keep a shadow copy.

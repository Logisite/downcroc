# 12 - Back up and come back

**What to build:** one command produces a single bundle of the database, content, vault and
configuration with a manifest and per-file hashes. Restore verifies, stages, checks integrity and
referenced content, then swaps by rename. A bundle whose schema revision is unknown is refused by
name. An interrupted restore leaves a marker and resolves on the next start.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] a populated install backs up, is wiped, and restores to identical counts with a working queue
- [ ] a tampered file is named before anything is extracted
- [ ] a bundle from an unknown revision is refused and the live data is untouched
- [ ] an interrupted restore leaves `restore.pending` and the next start finishes or aborts cleanly
- [ ] the previous data directory is kept beside the new one, named in the result
- [ ] the restored daemon starts locked and opens with the original password

**Logs:** the events this ticket introduces. A refused restore is a warning with both revisions
named, never a silent no-op.

- `backup.created` path, files, bytes, duration_ms
- `backup.verified` files, ok
- `backup.verify_failed` file
- `restore.staged` path, files
- `restore.swapped` previous, duration_ms
- `restore.refused` revision, reason
- `restore.resumed` marker

**Commit:** `feat(backup): add bundle create, verify, staged restore`

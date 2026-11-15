---
title: uninstall
commands: [uninstall]
flags: [--purge]
concepts: []
screens: []
---

# uninstall

`uninstall` removes a managed downcroc installation (its launchers and installed application files). By default it keeps your configuration, data, and state so they can be reused by a future install; `--purge` removes them as well.

`uninstall` only operates on a managed installation created by the supported install scripts/layout. Running it from a non-managed install (for example a checkout or an environment you created yourself) is refused with guidance.

## Usage

```text
downcroc uninstall [--purge] [--yes]
```

- `--purge` also removes configuration, data, and state directories (and associated keyring/vault material as applicable).
- `--yes` skips the confirmation prompt.

## Behavior

- If the daemon is running, it is stopped before uninstalling.
- Removes the managed installation’s launchers and application trees.
- Without `--purge`, configuration, data, and state are kept. The command reports what was removed and notes that config/data/state were kept (and that `--purge` removes them).
- With `--purge`, configuration, data, and state directories are removed as well. **Purging is irreversible** for local data not backed up elsewhere.

Because uninstall (especially with `--purge`) removes software and potentially data, it requires confirmation unless `--yes` is given.

## Output

- Default: reports how many items were removed and their paths, and whether data was kept or purged.
- With `--json`: prints the result (removed items, data kept/purged, and whether the service was stopped).

## Common flags

`--json`, `--no-input`, `--yes`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc uninstall` — remove the managed install but keep config, data, and state.
- `downcroc uninstall --purge` — remove the install and all local config/data/state.

## See also

- [../20-backup/backup.md](../20-backup/backup.md) — back up data before purging
- [../01-service/service.md](../01-service/service.md) — stop the daemon
- [../24-update/update.md](../24-update/update.md) — update a managed install
- [../part-i/03-keeping-it-running/where-is-my-stuff.md](../part-i/03-keeping-it-running/where-is-my-stuff.md) — where config/data/state live

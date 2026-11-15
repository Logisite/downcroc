---
title: Vault log events
commands: []
flags: []
concepts: [vault]
screens: []
---

# Vault log events

Events emitted around the credential [[vault]] (create, unlock, lock, and vault storage). Primary emitters: `src/downcroc/core/vault/service.py`, `src/downcroc/core/vault/file.py`.

- `vault.created` (**info**) — a new vault was created, installed, and left unlocked. Emitted by the vault service after initialization succeeds.
  - `duration_ms`: time taken to create/derive/write, in milliseconds.

- `vault.unlocked` (**info**) — the vault was unlocked successfully.
  - `duration_ms`: time taken to open/derive, in milliseconds.

- `vault.locked` (**info**) — the vault was locked (key material cleared). Emitted on explicit lock and on clean shutdown paths that lock the vault.
  - `reason`: why it was locked (as provided by the caller, e.g. an explicit lock or a shutdown reason).

- `vault.unlock_failed` (**warning**) — an unlock attempt failed because the password was incorrect. Emitted after recording the failure.
  - `attempts_left`: remaining attempts before throttling/delay applies (derived from configured free attempts and failures).

- `vault.derive_failed` (**error**) — key derivation for the vault failed.
  - typically includes `reason` / error detail (see the record).

- `vault.read_failed` (**error**) — reading the vault file/data failed.
  - typically includes `reason` / error detail.

- `vault.write_failed` (**error**) — writing vault data failed.
  - typically includes `reason` / error detail.

- `event.publish_failed` (**error**) — publishing a vault-related event to the event bus failed (the vault operation itself is logged separately).
  - `event`: the event name that failed to publish.
  - `reason`: the error.

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../04-vault/vault.md](../../04-vault/vault.md) — `downcroc vault` command behavior
- [../../02-status/status.md](../../02-status/status.md) — vault state in overall status

---
title: Policy and configuration log events
commands: []
flags: []
concepts: [allowance, sending_window, jitter, max_in_flight]
screens: []
---

# Policy and configuration log events

Events for send policy changes/resolution and configuration reloads. Primary emitters: `src/downcroc/core/policy/service.py`, `src/downcroc/core/policy/changes.py`, `src/downcroc/core/config_service.py`.

## Send policy

- `policy.changed` (**info**) — a send policy was changed (set/updated).
  - Includes fields identifying the scope and the changed values as emitted by the policy service.

- `policy.cleared` (**info**) — a send policy override was cleared.
  - Includes scope/identifier fields as emitted.

- `policy.resolved` (**info**) — the effective policy was resolved/logged in a resolution path.
  - Includes resolved values and/or sources as emitted.

## Configuration

- `config.reloaded` (**info**) — configuration was reloaded.
  - `changed`: what changed (as reported by the reload).

- `config.rejected` (**warning**) — a configuration change or load was rejected/invalid.
  - `field`: the field involved (when applicable).
  - `reason`: why it was rejected.

## Configuration

- `config.loaded` (**info**) — configuration was loaded (e.g. on startup).
  - Fields as emitted (such as path/source).

- `config.reloaded` (**info**) — configuration was reloaded after a change or file update.
  - `changed`: list of changed field paths (when available).

- `config.invalid` (**warning/error**) — configuration could not be loaded/parsed/validated.
  - `field` and `reason` (and path) as emitted.

- `config.reload_failed` (**error**) — reloading configuration failed unexpectedly.
  - `error`: exception/type name (and detail as emitted).

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../11-sending/sending.md](../../11-sending/sending.md) — global send policy
- [../../07-account/account.md](../../07-account/account.md) — per-account policy
- [../../17-config/config.md](../../17-config/config.md) — configuration commands
- [jobs-dispatch.md](jobs-dispatch.md) — dispatch behavior affected by policy (e.g. allowance)

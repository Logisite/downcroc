# 19 - Robust install and update self-healing

Part of the install/update hardening work. This plan owns the decision and
the phase breakdown for making the managed downcroc installation survive
interpreter churn (for example a 3.14 → 3.15 base-Python upgrade) without
leaving the user with a dangling launcher.

It builds on the failure we hit live: after the Python minor version moved,
`downcroc` stopped with

```text
exec: Failed to execute process '/home/logisiteau/.local/bin/downcroc':
The file specified the interpreter '/home/logisiteau/.local/share/downcroc/venv/bin/python',
which is not an executable command.
```

and a second-order failure where the interpreter resolved again but the venv
site-packages no longer contained the package.

## The managed layout

```text
<prefix>/share/downcroc/venv/bin/python{,3,3.x}   symlinks into the base interpreter
<prefix>/share/downcroc/venv/bin/downcroc          pip console script, shebang -> venv/bin/python
<prefix>/bin/downcroc                              -> share/downcroc/venv/bin/downcroc
<prefix>/share/downcroc/venv/pyvenv.cfg           home / version / base-executable
<prefix>/share/downcroc/venv/lib/python3.X/site-packages
```

The source of truth for the intended base interpreter is `pyvenv.cfg`
(`home`, `version`, `executable`). The source of truth for the launcher is the
pip console script plus the `<prefix>/bin/downcroc` symlink.

## Root cause

`downcroc update` performs a single `python -m pip install --upgrade <wheel>`
inside the managed venv and stops there. It does not:

1. verify the interpreter chain for the shebang / venv links after the base
   interpreter moves;
2. verify that the venv still resolves to a usable interpreter and contains the
   installed package (site-packages can be empty or stale after partial failures);
3. repair links before/after install or fall back to a clean venv rebuild;
4. surface a deterministic next step (install Python 3.14+ / reinstall) instead of
   leaving a dangling interpreter.

## Design decisions

- **Single health/repair primitive.** Add one routine that resolves the managed
  venv interpreter, normalizes the `python` / `python3` / `pythonX.Y` links, and
  runs an import probe for `downcroc.cli.main`. Callers: update, installers, doctor,
  and an explicit `downcroc repair`.
- **Resolve, do not guess.** Prefer `pyvenv.cfg`'s base executable; if absent, pick a
  supported base interpreter (Python 3.14 or newer) that exists. Never write links to
  a guessed path silently.
- **Healthy = runnable.** The install is healthy only when the console script shebang
  resolves to a real interpreter *and* the venv python imports `downcroc`. Otherwise the
  status is `needs_reinstall` (or `unrecoverable` when no supported interpreter exists).
- **Relink vs rebuild.** Relink when the chain is dangling or cyclic but the resolved
  interpreter and site-packages are consistent. Rebuild the venv from scratch when the
  minor-version/site-packages layout is inconsistent or when the resolved base differs
  materially from the venv version. Do not silently rebuild on every update.

## Phases

### Phase 1 - Repair primitive

- Implement interpreter-link normalization + resolution + import probe.
- Unit tests: dangling `python`, cyclic `python -> python3 -> python3`, missing base
  executable, present `pyvenv.cfg` with missing base, empty site-packages / import probe
  failure (rebuild path).

### Phase 2 - Update self-healing

- `downcroc update`: preflight health, install through the resolved venv interpreter, post
  install normalize + probe, on failure attempt recovery (clean venv + wheel + deps), restart
  daemon only after a healthy install.
- Keep checksum + release flow unchanged.

### Phase 3 - Installers and doctor

- `scripts/install.sh` / `scripts/install.ps1`: after `python -m venv` + wheel install, verify
  links (`"$VENV/bin/downcroc" --version`) and fail with actionable message if base python is
  missing.
- `downcroc doctor`: add managed-install health checks (dangling/cyclic links, base mismatch,
  unimportable package) with a concrete fix hint.

### Phase 4 - Command and surface

- Add `downcroc repair` that runs the health/repair routine (relink, rebuild if needed) and
  reports what changed. Doctor may call it.

### Phase 5 - Tests and docs

- Tests for update path with a deliberately broken venv (relink / rebuild), installer smoke,
  doctor detection.
- Document in the install/update docs page: what downcroc repairs, when a full reinstall is
  needed, and the supported Python floor.

## Acceptance criteria

- With a dangling venv interpreter chain, running the update/repair path results in a working
  `downcroc` (console script executes, `--version` prints, import probe passes).
- After a normal update, no manual symlink surgery is required.
- Doctor can explain the failure and the next step.

## Non-goals

- Changing data, credentials, auth flows, or provider behavior.
- Adding cross-user concurrency or multi-daemon management.

## Open questions

1. Should the repair live in a new CLI command (`downcroc repair`) now, or be surfaced only
   through doctor/update until the UX is agreed?
2. Should the update flow rebuild the venv automatically on Python minor-version drift, or only
   repair links and let doctor flag drift?

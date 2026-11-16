# downcroc

Always-on local mail daemon. Python 3.14, uv, FastAPI, SQLite, imap-tools.
The daemon and HTTP API exist; there is no TUI client in this repo yet.

## Platform scope

**macOS is out of scope for release 1: no CI leg, no artifact, no installer, and no support
commitment. Never spend time removing macOS code paths that already exist. The darwin
fallbacks in `runtime/paths.py` and `runtime/service/units.py` stay untouched; do not delete
them, and do not refactor around them. Plan and ticket text says Linux and Windows; the code
keeps working wherever it already works.**

## Tooling

- Use uv for every Python command: `uv run ...`, `uv run ruff ...`. Never call
  `.venv/bin/python`, `.venv/bin/ruff`, or other virtualenv binaries directly.
- Use normal file edits and standard commands. No hacks, wrappers, or binary
  shortcuts around the toolchain.
- Add and remove packages with `uv add` / `uv remove`. Never hand-edit the
  dependency tables or `uv.lock`.
- Ruff runs with its shipped defaults. There is no `[tool.ruff]` config and you
  must not add one. Fix findings in code instead of suppressing them.
- Do not write to linter override or exception allowlist files (for example docs
  log-event exception `.txt` files) to silence checks; fix the underlying issue
  or report a linter bug.
- After a change, run in this order. Fix first, then check once:

```sh
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
```

Do not run the plain check twice; `--fix` already resolved what it can.

If an error cannot be found from the logs, the logs are not doing their job.
Unexpected failures must log the event, ids, error class, detail, and traceback.

- Run `uv lock --check` and `uv run python -m compileall -q src` as
  fast integrity checks.

## Vertical slices

**Write additional code in vertical slices. Each slice owns one feature end to
end, while shared primitives still live in their layer. If a slice grows past
one responsibility, split it by sub-behavior, not by layer alone. Prefer this
over spreading one feature's logic across many files or attempting a complete
refactor.**

**As time goes on, move useful horizontal primitives into their respective
vertical slices. The goal is a solid repository architecture by version 1.5,
without a disruptive refactor.**

**Vertical does not mean duplicating primitives. If two slices need the same
behavior, extract one shared primitive in its layer and reuse it. Every change
must leave the code better than it was found.**

## Developer experience

Prefer reproducible CLI workflows and generated tooling over hand-rolling
project files. Optimise for DX that another maintainer can repeat from the
docs.

- Generate schema revisions with the Alembic CLI, never by hand:

```sh
DOWNROC_DB_URL=sqlite:////tmp/downcroc-alembic.db uv run alembic upgrade head
DOWNROC_DB_URL=sqlite:////tmp/downcroc-alembic.db \
  uv run alembic revision --autogenerate -m "describe the change"
```

Review the generated file, remove unrelated autogenerate noise, add data
seeding or a downgrade only where the project template does not, then run
`uv run alembic upgrade head` against a fresh database before committing.

- Use the project commands for formatting, linting, dependency changes,
  service control, and inspection. Do not replace a supported command with a
  manual edit or a one-off script.
- When a CLI path is awkward, improve the CLI or its docs instead of teaching
  the next person a workaround.

## Running and checking

```sh
uv run downcroc serve              # foreground daemon
uv run downcroc service start      # detached
uv run downcroc service status
uv run downcroc service stop
uv run downcroc logs --follow
uv run downcroc logs --event watcher. --json
uv run downcroc openapi -o openapi.json
uv run pytest                      # black-box acceptance suite
```

- Acceptance is proven by black-box tests that start the real daemon and drive
  it over real HTTP, storage, and logs. The suite lives in `tests/` and runs
  with `uv run pytest`.
- Fake only external SMTP, IMAP, and OAuth servers. Do not mock daemon modules,
  service objects, SQLite, or the HTTP layer.
- Do not add internal-only unit tests unless explicitly asked. The external
  suite is the acceptance gate.
- While working on a ticket, run only that ticket's test file, for example
  `uv run pytest -q tests/test_batches.py`. Run the full suite once at the end
  after all tickets are complete, not after every ticket.
- When a check needs detail, write the full output to a file once and query
  that file. For pytest:

```sh
uv run pytest -vv tests/test_lifecycle.py > /tmp/opencode/pytest.log 2>&1
grep -n "FAILED\|assert\|Error" /tmp/opencode/pytest.log
```

  Do not rerun the suite to see a failure, and do not pipe through `tail` in a
  way that discards the traceback.
- Isolate tests and live checks so they do not touch real config, database,
  vault, or logs:

```sh
HOME=/tmp/opencode/downcroc-home \
XDG_CONFIG_HOME= XDG_DATA_HOME= XDG_STATE_HOME= \
UV_CACHE_DIR=/root/.cache/uv \
uv run downcroc serve
```

- The daemon binds `127.0.0.1:8765` by default and starts locked. Unlock through
  `POST /api/vault/unlock`; a clean stop locks the vault again.
- The JSONL log is under the XDG data directory at
  `downcroc/logs/downcroc.jsonl` (`~/.local/share` by default).

## Layout and boundaries

- `src/downcroc` is the package. The CLI entry point is
  `downcroc.cli.main:main`.
- `core/bootstrap.py` is the composition root. Wire services there, not in
  routes or feature modules.
- `api/app.py` owns the lifespan: build services, start the event bus, then stop
  inbound workers, lock the vault, and close the bus on shutdown.
- `runtime/service/lifecycle.py` owns the single-instance lock, `service.json`,
  start, stop, and signal handling.
- The daemon owns all state. The API is loopback-only and requires the per-run
  bearer token from `daemon.token`; only `/api/health` and the OAuth callback are
  public. Never bind or expose it beyond loopback.
- `api/auth.py` owns bearer auth and Host/Origin validation, and `cli/client.py`
  attaches the token. Credentials must never reach logs, events, API responses,
  error messages, or backup bundles.
- `plan/` is the design. `.scratch/downcroc/issues` holds the current tickets and
  is git-ignored. Code wins when they drift; update `plan/` when behavior changes.
- Schema changes need a new Alembic revision under
  `src/downcroc/store/db/migrations/versions`. The
  daemon runs `upgrade head` at startup. `alembic.ini`'s URL is a development
  placeholder; runtime uses the database under the XDG data directory.
- IMAP watcher threads must not touch SQLite. They hand work to the ingester;
  preserve that boundary when changing inbound code.
- Provider declarations live in `src/downcroc/providers/declarations/*.toml`.
  User overrides go in the config directory; a new declaration should not need a
  code change.
- Credentials must never reach logs, events, API responses, or error messages.

## Terminal UI design

Keep Textual as the invisible engine for the docs browser and future terminal
apps, and go all-in on custom Rich widgets instead of raw Textual chrome.
`cli/docs/blocks.py` is the start of our design system: the theme plus a few
primitives (card, keybar, hero, code panel, callout). Never use a stock
Textual widget without restyling it through that system. This gets the
distinctive downcroc look in days, without betting the app on a homegrown
compositor; a full raw-Rich rebuild is a multi-week engine project with
flicker risk, and its payoff over a well-skinned Textual is mostly ideology.

## Code style

- Keep code modular: one responsibility per module or service. Keep `domain`
  pure, adapters isolated, and orchestration in `core`.
- Keep every Python source and test file under 400 lines. A file that grows past
  that is a signal to split it by responsibility, not to compress it. Packages
  with several focused modules are preferred over one god module.
- Keep functions short and lines inside Ruff's default formatting. Break long
  expressions into named helpers instead of writing dense one-liners.
- Few comments. No `TODO` or `FIXME`. Prefer configuration over hardcoded limits.
- No em dashes in code, output, docs, or commits.
- Daemon diagnostics go through `EventLogger` with structured fields
  (`log.info("event.name", field=value)`), not `print`.
- One commit per ticket after live checks: `type(scope): lowercase summary`,
  under 72 characters, no body, footers, or emoji.

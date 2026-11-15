---
title: Inbound and watcher log events
commands: []
flags: []
concepts: []
screens: []
---

# Inbound and watcher log events

Events for mailbox watching, inbound sync/sweeps, and inbound source selection. Primary emitters: `src/downcroc/core/inbound/service.py`, `src/downcroc/core/inbound/watcher.py`, `src/downcroc/core/inbound/worker.py`, `src/downcroc/core/inbound/idle.py`, `src/downcroc/core/inbound/sweep.py`, `src/downcroc/core/inbound/gmail_watcher.py`.

## Watcher lifecycle and state

- `watcher.paused` (**info**) — inbound watching paused (for example due to connectivity loss).
  - `reason`: why it paused (e.g. `connectivity`).

- `watcher.resumed` (**info**) — inbound watching resumed after a pause condition cleared.
  - `reason`: why it resumed (e.g. `connectivity`).

- `watcher.stopped` (**warning**, log; also published/queued as a state/event in some paths) — a watcher stopped or died. Emitted from supervisor/runner/Gmail-watcher paths when a watcher thread ends or fails.
  - `account`: account id.
  - `reason`: stop/failure reason (e.g. `watcher_died`, source switch, shutdown-related reasons, or a specific failure reason).
  - `retry_in_s`: delay before retry/restart (when applicable, e.g. on unexpected death).
  - `cause`: additional cause detail in some runner paths (e.g. loop exit/error vs explicit stop reason).

- `watcher.supervisor_failed` (**error**) — the inbound supervisor hit an unexpected error but continued running (the supervisor must survive).
  - `error`: exception/type name.
  - `detail`: error detail.

- `watcher.idle_wake` (**info**) — an idle IMAP watcher was woken.
  - `account`: account id.
  - `reason`: wake reason.

## Inbound source selection

- `inbound.source_switch` (**info**, log; may also be queued as a watcher event) — the inbound source for an account changed or was selected in a way that is recorded (for example switching to `gmail_api` in supported configurations).
  - Includes fields such as `account` and the selected source/mode/reason as emitted.

- `inbound.idle_cap` (**info**, log; also queued as a watcher event) — the idle-watcher fleet cap was reached, so the account falls back (e.g. to IMAP polling) rather than holding an idle slot.
  - `account`: account id.
  - `cap`: the idle fleet cap.
  - `fallback`: the fallback mode (e.g. `imap_poll`).

## Sweeps and provider-specific watchers

Inbound sweep and Gmail-watcher paths emit additional info/warning/error records for sync progress, polling, history/changes, and failures. These are operation- and account-specific; consult the matching log line (or `--json`) for the exact `event` name and fields in that case.

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../07-account/account.md](../../07-account/account.md) — inbound source, sync, watch controls
- [accounts-auth.md](accounts-auth.md) — account/auth issues that affect watching
- [../../part-i/04-mailboxes/broken-mailbox.md](../../part-i/04-mailboxes/broken-mailbox.md) — mailbox problems

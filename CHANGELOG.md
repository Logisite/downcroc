# Changelog

Downcroc follows a release-note file per version under [`release-notes/`](release-notes/). This
file is a short index. The release note is the canonical description of a release.

## 1.3.5.post1

Global table flags work before the command, and the update check is daily.

See [`release-notes/v1.3.5.post1.md`](release-notes/v1.3.5.post1.md).

## 1.3.5

Collects the post-`1.3.4` fixes and fixes the interactive tree's global flag toggles.

See [`release-notes/v1.3.5.md`](release-notes/v1.3.5.md).

See [`release-notes/v1.3.5.md`](release-notes/v1.3.5.md).

## 1.3.4.post4

List commands default to oldest first with a `--newest-first` flag to invert.

See [`release-notes/v1.3.4.post4.md`](release-notes/v1.3.4.post4.md).

## 1.3.4.post3

Restores level colours and full terminal width in the `logs --chain` view.

See [`release-notes/v1.3.4.post3.md`](release-notes/v1.3.4.post3.md).

## 1.3.4.post2

Adds `downcroc logs --chain`, a linked card view of log events with no truncated values.

See [`release-notes/v1.3.4.post2.md`](release-notes/v1.3.4.post2.md).

## 1.3.4.post1

Keeps boxed tables with wrapped cells as the default at every width; stacking is
now opt-in via `--stack`.

See [`release-notes/v1.3.4.post1.md`](release-notes/v1.3.4.post1.md).

## 1.3.4

Adds a cached hourly update check, `batch validate --followup`, stacked tables in
narrow terminals, and a global `--addresses` flag.

See [`release-notes/v1.3.4.md`](release-notes/v1.3.4.md).

## 1.3.3.post2

Follow-ups now thread reliably with the recipient across both SMTP and Gmail API sends.

See [`release-notes/v1.3.3.post2.md`](release-notes/v1.3.3.post2.md).

## 1.3.3.post1

Describe this release.

See [`release-notes/v1.3.3.post1.md`](release-notes/v1.3.3.post1.md).

## 1.3.3.post1

Release automation now publishes the repository release note as the GitHub release body.

See [`release-notes/v1.3.3.post1.md`](release-notes/v1.3.3.post1.md).

## 1.3.3

Backfill searches Trash before calling a hole missing, adds the `downcroc backfill`
diagnostics command, and shows log times in your local timezone.

See [`release-notes/v1.3.3.md`](release-notes/v1.3.3.md).

## 1.3.2.post8

Backfill drains continuously, caches the Sent sweep, and logs sweep progress.

See [`release-notes/v1.3.2.post8.md`](release-notes/v1.3.2.post8.md).

## 1.3.2.post7

Describe this release.

See [`release-notes/v1.3.2.post7.md`](release-notes/v1.3.2.post7.md).

## 1.3.2.post6

Describe this release.

See [`release-notes/v1.3.2.post6.md`](release-notes/v1.3.2.post6.md).

## 1.3.2.post5

Describe this release.

See [`release-notes/v1.3.2.post5.md`](release-notes/v1.3.2.post5.md).

## 1.3.2.post4

Describe this release.

See [`release-notes/v1.3.2.post4.md`](release-notes/v1.3.2.post4.md).

## 1.3.2.post3

Self-healing managed installs: interpreter repair, `downcroc repair`, doctor check, robust update, and structured migration-failure logging.

See [`release-notes/v1.3.2.post3.md`](release-notes/v1.3.2.post3.md).

## 1.3.2.post2

Gmail API follow-up threading fix.

- Follow-up replies sent via the Gmail API now pass the provider `threadId`, so they stay in the original Gmail conversation
- Gmail API sends record provider thread ids for follow-up chain resolution
- Gmail API inbound sweeps can attribute replies by matching Gmail `threadId` to sent attempts

See [`release-notes/v1.3.2.post2.md`](release-notes/v1.3.2.post2.md).

## 1.3.2.post1

Follow-up visibility fix.

- `batch followups status`, `batch thread`, `batch list --parents`, and follow-up outlook now surface immediate/ad-hoc sent child follow-up steps that were previously missing from parent views

See [`release-notes/v1.3.2.post1.md`](release-notes/v1.3.2.post1.md).

## 1.3.2

Follow-up visibility and CLI improvements for downcroc users.

- Follow-ups: `downcroc followups due` outlook, `downcroc batch thread <batch_id>` (with `--recipient`/`--all`), and `downcroc batch list --parents --sort {recent,stale}` with summaries and `next_due_at`
- CLI: real sender shown on jobs, card-style `mail show`/`mail thread`, relative `s/m/h/d/mo` times (ISO in JSON), nested `docs --list` tree, and improved docs browser layout on narrow terminals
- API: `GET /api/followups/outlook`, `GET /api/batches/{id}/thread`, and follow-up summaries in parent batch listing
- Fix: preserve dispatch seat reason and rotate SMTP seats when idle
- Docs: new command docs plus expanded bundled book (glossary, Part III references, more Part I/II content), cleanup, and README refresh
- Tooling: `scripts/bump_version.py` for version bumps and release scaffolding

See [`release-notes/v1.3.2.md`](release-notes/v1.3.2.md).

## 1.3.1

Reliability release for vault, account state, manual sending, provider quota handling, attempts,
logging, SMTP seats, and follow-up declarations.

- archived accounts keep their credentials through vault unlock
- `credential_present` is derived from the vault
- manual job create and send work end to end
- background credential preflight after unlock
- provider response classification for SMTP and Gmail
- every reserved send attempt is finalized or reconciled
- sticky SMTP seat with API fallback
- structured API, auth, daemon, policy, OAuth, watcher, and send logs
- `downcroc logs --addresses`
- retroactive follow-up declarations

See [`release-notes/v1.3.1.md`](release-notes/v1.3.1.md).

## 1.3.0.post2

Stats rebuild compatibility and manual send attribution fixes.

See [`release-notes/v1.3.0.post2.md`](release-notes/v1.3.0.post2.md).

## 1.3.0.post1

Automatic send attribution and manual job fixes.

See [`release-notes/v1.3.0.post1.md`](release-notes/v1.3.0.post1.md).

## Earlier releases

See the [`release-notes/`](release-notes/) directory for the complete history.

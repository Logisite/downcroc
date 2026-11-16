# Changelog

Downcroc follows a release-note file per version under [`release-notes/`](release-notes/). This
file is a short index. The release note is the canonical description of a release.

## 1.3.2

Follow-up outlook and batch thread views, improved mail/CLI reading, and docs updates.

- `downcroc followups due` and `downcroc batch thread <batch_id>`
- parent `batch list --parents/--sort` with follow-up summaries
- relative `s/m/h/d/mo` CLI times; ISO timestamps in JSON
- card-style `mail show`/`mail thread` and nested `docs --list` tree
- new read APIs: `GET /api/followups/outlook`, `GET /api/batches/{id}/thread`

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

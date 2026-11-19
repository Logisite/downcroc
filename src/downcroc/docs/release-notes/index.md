---
title: Release notes
description: What changed in each release and what to do before upgrading.
tags: [release, changelog]
audience: user
status: stable
since: 1.3.4.post3
order: 0
terminal:
  summary: Current release is 1.3.4.post3.
---

# Release notes

## 1.3.4.post3

Restores level colours and full terminal width in the `logs --chain` view.

See the full note in `release-notes/v1.3.4.post3.md` at the repository root.

## 1.3.4.post2

Adds `downcroc logs --chain`, a linked card view of log events with no truncated values.

See the full note in `release-notes/v1.3.4.post2.md` at the repository root.

## 1.3.4.post1

Keeps boxed tables with wrapped cells as the default at every width; stacking is
now opt-in via `--stack`.

See the full note in `release-notes/v1.3.4.post1.md` at the repository root.

## 1.3.4

Adds a cached hourly update check, `batch validate --followup`, stacked tables in
narrow terminals, and a global `--addresses` flag.

See the full note in `release-notes/v1.3.4.md` at the repository root.

## 1.3.3.post2

Follow-ups now thread reliably with the recipient across both SMTP and Gmail API sends.

See the full note in `release-notes/v1.3.3.post2.md` at the repository root.

## 1.3.3.post1

Release automation now publishes the repository release note as the GitHub release body.

See the full note in `release-notes/v1.3.3.post1.md` at the repository root.

## 1.3.3

Backfill searches Trash before calling a hole missing, adds the `downcroc backfill`
diagnostics command, and shows log times in your local timezone.

See the full note in `release-notes/v1.3.3.md` at the repository root.

## 1.3.2.post8

Backfill drains continuously, caches the Sent sweep, and logs sweep progress.

See the full note in `release-notes/v1.3.2.post8.md` at the repository root.

## 1.3.2.post7

Describe this release.

See the full note in `release-notes/v1.3.2.post7.md` at the repository root.

## 1.3.2.post6

Describe this release.

See the full note in `release-notes/v1.3.2.post6.md` at the repository root.

## 1.3.2.post5

Describe this release.

See the full note in `release-notes/v1.3.2.post5.md` at the repository root.

## 1.3.2.post4

Describe this release.

See the full note in `release-notes/v1.3.2.post4.md` at the repository root.

## 1.3.2.post3

Self-healing managed installs: interpreter repair, `downcroc repair`, doctor check, robust update,
and structured migration-failure logging.

See the full note in `release-notes/v1.3.2.post3.md` at the repository root.

## 1.3.2.post2

Fixes Gmail API follow-up threading so replies stay in the original conversation. Gmail API sends
now pass and record provider thread ids, and inbound Gmail API sweeps can attribute replies by
matching the Gmail thread id.

See the full note in `release-notes/v1.3.2.post2.md` at the repository root.

## 1.3.2.post1

Fixes follow-up visibility so immediate/ad-hoc sent child follow-up steps appear in `batch followups
status`, `batch thread`, `batch list --parents`, and the follow-up outlook.

See the full note in `release-notes/v1.3.2.post1.md` at the repository root.

## 1.3.2

Follow-up visibility and CLI improvements: `followups due` outlook, `batch thread` view, and
parent `batch list --parents/--sort` summaries; real sender on jobs, card-style `mail show`/`mail
thread`, relative CLI times, nested `docs --list`, and a narrower docs browser layout. Includes
new read APIs, a dispatch seat-rotation fix, expanded bundled docs, and `scripts/bump_version.py`.

See the full note in `release-notes/v1.3.2.md` at the repository root.

## 1.3.1

Reliability release for vault, account state, manual sending, provider quota handling, attempts,
logging, SMTP seats, and follow-up declarations.

See the full note in `release-notes/v1.3.1.md` at the repository root.

## Upgrade

The daemon runs new migrations at startup when a release includes them. Restart a user service
after upgrading. No new config is required unless noted in the release note.

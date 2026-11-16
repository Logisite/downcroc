---
title: Release notes
description: What changed in each release and what to do before upgrading.
tags: [release, changelog]
audience: user
status: stable
since: 1.3.2.post1
order: 0
terminal:
  summary: Current release is 1.3.2.post1.
---

# Release notes

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
after upgrading. `1.3.2.post1` requires no database migrations or configuration changes.

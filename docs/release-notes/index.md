---
title: Release notes
description: What changed in each release and what to do before upgrading.
tags: [release, changelog]
audience: user
status: stable
since: 1.3.1
order: 0
terminal:
  summary: Current release is 1.3.1.
---

# Release notes

## 1.3.1

Reliability release for vault, account state, manual sending, provider quota handling, attempts,
logging, SMTP seats, and follow-up declarations.

See the full note in `release-notes/v1.3.1.md` at the repository root.

## Upgrade

The daemon runs new migrations at startup. Restart a user service after upgrading. No new config
is required.

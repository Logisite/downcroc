---
title: Security model
description: Where credentials live and what the loopback API trusts.
tags: [security, vault, api]
audience: security
status: stable
since: 1.3.1
order: 10
terminal:
  summary: Credentials stay in the encrypted vault. The API is loopback only.
---

# Security model

- Credentials live in the encrypted vault, not in SQLite.
- The API binds to loopback and requires the per-run bearer token.
- Secrets are not written to logs, events, API responses, or backups in plaintext.
- The daemon should run as your user, not as root.

## Vault

The vault file is encrypted with a key derived from the master password. Locking the vault drops
the key. A clean stop locks it again.

## API

Only `/api/health` and the OAuth callback are public. Every other route checks the bearer token
and the Host and Origin headers.

## Logs

Credential, token, password, and authorization fields are scrubbed at the logging boundary.

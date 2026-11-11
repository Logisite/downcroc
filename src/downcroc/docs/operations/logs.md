---
title: Logs
description: Read structured daemon events, follow them, and resolve account addresses.
tags: [logs, events, diagnostics]
audience: operator
status: stable
since: 1.3.1
order: 20
terminal:
  summary: Structured JSONL events plus a pretty terminal view.
---

# Logs

```sh
downcroc logs --follow
downcroc logs --level warning --since 15m
downcroc logs --addresses --event account. --since 1h
downcroc logs --json
```

The JSONL file is never rewritten by the CLI. `--addresses` changes only the pretty rendering.
With `--json`, the account id stays and `account_address` is added.

## Common events

- `api.request_failed`
- `api.auth_rejected`
- `account.auth_check_summary`
- `dispatch.smtp_seat`
- `job.sent`
- `transport.attempt`
- `smtp.rejected`
- `gmail.rejected`
- `followup.created`

## When the daemon is down

The logs command reads the JSONL offline. If address resolution needs the daemon and it is down,
the command prints ids and one warning to stderr.

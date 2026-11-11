---
title: CLI overview
description: The command groups and the shortest path through them.
tags: [cli, commands]
audience: user
status: stable
since: 1.3.1
order: 10
terminal:
  summary: Install, connect, send, inspect, and operate.
---

# CLI overview

```sh
downcroc init
downcroc account add
downcroc account connect
downcroc batch submit
downcroc job list
downcroc doctor
downcroc logs
downcroc stats summary
downcroc backup
```

## Command groups

| Group | Purpose |
|---|---|
| `account` | add, connect, verify, pause, archive, transport |
| `batch` | validate, preview, submit, approve, cancel, delete |
| `job` | list, show, send, pause, cancel, delete |
| `mail` | list, threads, show, attachments, sync |
| `docs` | read the book in the terminal or browser |
| `doctor` | installation, transport, capacity, and inbound checks |
| `logs` | query and follow the JSONL log |
| `service` | install, start, stop, status, pause, resume |
| `stats` | summary, hourly, daily, batches, accounts, rebuild, prune |

The interactive command surface is `downcroc` with no arguments.

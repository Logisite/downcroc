---
title: Troubleshooting
description: Start with doctor, then read the event that names the failure.
tags: [troubleshooting, doctor, logs]
audience: operator
status: stable
since: 1.3.1
order: 0
terminal:
  summary: Doctor first, logs second, event code third.
---

# Troubleshooting

## First checks

```sh
downcroc status
downcroc doctor
downcroc logs --level warning --since 30m
```

## Account needs reconnect

The account credential is missing or the provider rejected it. Reconnect the account.

## Sending is paused

A service, account, batch, or job hold is active. The ETA and the event name the scope.

## Slot plan allows no transport

The account is seated for SMTP but the binding is unhealthy, or it is unseated and has no healthy
API binding. Check `downcroc doctor transports`.

## Follow-up did not send

Check the parent has a sent anchor, the step is due, the recipient has not replied or bounced,
and the sender account is still eligible.

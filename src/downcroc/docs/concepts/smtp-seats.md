---
title: SMTP seats
description: How seats, rotation, and API fallback work.
tags: [smtp, seats, capacity, dispatch]
audience: operator
status: stable
since: 1.3.1
order: 35
related:
  - operations/doctor.md
terminal:
  summary: Seats are transport reservations, not account status.
---

# SMTP seats

Seats are transport reservations, not account status.

## How a seat is elected

At most `dispatch.smtp_seats` SMTP connections are open. A sticky seat is held until a cap,
failure, or batch drain.

```sh
downcroc doctor capacity
```

## Failover

A failed seat is replaced on the next cycle. The replacement continues the round-robin order, so
the same account is not always first.

## API fallback

A pinned account that is not seated still sends through the Gmail API binding when one is
healthy. Pinning means the account, not the transport.

!!! warning "Seat width"
    Raising `smtp_seats` above 3 increases account risk. It does not create parallel SMTP
    throughput.

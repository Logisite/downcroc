---
title: Seats and threads
commands: [status, batch.show, job.show, config.show]
concepts: [thread, batch, job, daemon]
---

# Seats and threads

This chapter explains two different ideas that share a page because they both
shape how sending feels: **seats and lanes** control how much work can move at
once, and **threads** control whether follow-ups and replies stay attached to the
right conversation.

For the status words that result from these mechanics, see [States](33-states.md).
For the end-to-end flow of a send, see [Pipeline](30-pipeline.md).

## Capacity: lanes and seats

downcroc computes sending capacity from live state: which [[account]]s are
connected and eligible, which bindings/transports are usable, current holds and
quota, and the active slot plan. Capacity is a read-time view, not a stored
promise.

There are two kinds of throughput to keep apart:

- **API lanes** come from non-seat (API-style) bindings and can represent
  concurrent capacity where the transport allows it, subject to limits and
  configuration.
- **SMTP seats** are different. An SMTP seat is one connection/rotation slot and
  SMTP sending is treated as serial: only one SMTP send is in flight per seat.
  Adding SMTP seats widens the rotation (more mailboxes can take turns), which
  can shorten the serial duration over a set of messages, but it does not turn
  SMTP into parallel sends on the same path.

Effective throughput is derived from active API lanes plus the active SMTP
rotation (when SMTP is in play). When there is no eligible binding/capacity for
messages, the system reports that work is blocked by the lack of a usable
binding rather than inventing progress.

## SMTP rotation and seat behavior

SMTP-capable accounts can be arranged into a slot plan/queue. Some accounts may
be active in the rotation while others wait, depending on plan and health.
Configuration controls how that rotation behaves (see
[Configuration reference](38-config.md)): for example the number of SMTP seats,
whether a seat is “sticky”, and caps that cause a sticky seat to rotate (by
time, by successful SMTP send count, or after the current [[batch]] drains when
`smtp_seat_after_batch` is enabled). A sticky seat is only advanced by the
dispatcher. Capacity and show views can inspect the current plan without
changing the owner. A new owner is chosen from accounts with work, a usable SMTP
binding, and allowance left. The live transport list drives selection: an
account with only SMTP enabled carries more weight than one with both SMTP and
API enabled, and disabled or unhealthy bindings are excluded entirely.

The owner keeps the seat while it can use it and has work. It is relieved when
allowance runs out, its SMTP binding becomes unusable, a send fails, a
configured cap fires, or its work is finished. The next account is chosen from
the working fleet. The relieved account can be selected again when its issue is
cleared.

These knobs trade simplicity and pacing for distribution across mailboxes. They
do not bypass sending windows, daily allowance, holds, or other safety/policy
checks; they shape which eligible SMTP path is used when work can move.

## Dispatch, concurrency, and limits

The dispatcher runs in cycles, finds due/eligible work, and respects global and
per-account limits (such as in-flight limits and pacing/jitter policy). A job is
leased while `sending`, so concurrency controls determine how many attempts can
be active, not just how many jobs exist.

Service-level and per-scope pauses/holds reduce or stop what can be dispatched.
Capacity/selection views and events can reflect when throughput drops, when work
is held, or when a selection runs on a single sequential seat (and may advise
adding parallel-capable capacity where appropriate).

In short: **state says what a job is; capacity and limits say when it may move.**

## What “thread” means here

A thread is the chain that ties follow-up messages to the conversation started
by an earlier sent [[job]]. downcroc keeps that chain explicitly so a follow-up
can be sent as a reply in the same conversation rather than as an unrelated new
message.

Each outbound job carries identity needed for threading: a message id for the
message itself and links to its parent and thread root (the originating job of
the chain). When a follow-up is built, downcroc walks the chain from the current
anchor back to the root and derives the reply headers from it: the immediate
parent becomes the reply target, and the ordered message-id references form the
conversation chain.

## How follow-ups stay in the conversation

Follow-up planning chooses an anchor (the latest sent message in the chain that
the step should reply to) and constructs the thread chain for that recipient.
The derived follow-up job records its parent/root, reuses the chain’s message-id
references, and is built so its subject and headers continue the conversation
(for example, reply-style subject handling where applicable).

If the chain cannot be built safely — a missing parent/job/message id, a gap, or
an inconsistent link — the case is treated as `thread_broken` for that
recipient/step rather than sending a guess. That protects conversation integrity
but means the step cannot proceed for that case until the underlying issue is
resolved. Derived step status and logs surface these outcomes.

## Stop conditions and thread signals

Whether a follow-up should be sent also depends on signals observed on the
thread/recipient (such as replies or bounces) and on suppression/stop rules
configured for the campaign. If a stop or suppression condition applies, the
recipient is not sent that follow-up and is reported as skipped/suppressed with a
reason where available.

Threads therefore connect three things: **what** to send (the step/content),
**where** it attaches (the chain and headers), and **whether** it should still go
out (signals, suppression, and state). [Pipeline](30-pipeline.md) shows where
follow-up planning fits in the overall flow.

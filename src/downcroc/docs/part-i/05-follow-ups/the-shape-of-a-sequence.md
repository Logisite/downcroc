---
title: The shape of a sequence
commands: [batch.followups.status]
concepts: [follow_up]
screens: []
---

# The shape of a sequence

A follow-up is described as a [[follow_up_step|step]]: wait this long, then send
this, but only if it still makes sense. When you read or write a sequence, you
are really reading a few simple decisions repeated for each step.

## When and whether

Every step waits a number of days before it becomes due. `after_days` is that
wait (1–365), counted from the point the step follows. `when` says the condition:
`no_reply` sends only if the thread stayed quiet; `always` sends when due even if
there was a reply (subject to other stop rules). A step can also ask for
[[approval]] before it sends (`require_approval`), so downcroc prepares it but
waits for you.

## Content and identity

Each step has a `key`, a short name that identifies it in the sequence. The key
is how you refer to it later to inspect, change, or stop it; keys must be unique
where required and stay meaningful once used.

A step needs something to send: `text` or `html` (or both). `subject` is
optional — if you omit it, the follow-up is sent as a reply using the original
subject in reply form. This keeps the message in the same conversation.

## Writing it in a campaign file

In a campaign JSON, steps live in the top-level `followups` list, and a message
can carry per-recipient overrides for a step under `messages[].followups` keyed
by step key:

```json
"followups": [
  {
    "key": "nudge",
    "after_days": 3,
    "when": "no_reply",
    "text": "Just checking in on my earlier note.",
    "require_approval": false
  }
]
```

```json
"messages": [
  {
    "key": "m1",
    "to": { "email": "ana@example.com" },
    "subject": "Hello",
    "text": "Hi Ana, ...",
    "followups": { "nudge": { "skip": true } }
  }
]
```

An override may set `subject`, `text`, `html`, or `skip: true` for that
recipient and that step. It must name a step key that exists in `followups`.

## Adding it later: declarations

After a batch exists you can add a step as a [[follow_up_declaration]]. A
[[shared_declaration]] gives one schedule and shared content (plus optional
overrides by parent message key). A [[payload_declaration]] gives a `followup`
schedule block and an explicit `messages` list — one message per parent
recipient — so each person can receive specific content.

Those forms, and the rules for declaring, updating, removing, and retiring, are
detailed in Part II. The important idea is the same in every case: a named step,
a wait, a condition, and the message it will send as a reply.

⤷ adding a follow-up to work that already exists:
  [add-a-follow-up-to-a-batch.md](add-a-follow-up-to-a-batch.md)
⤷ stopping, skipping, and seeing why a step did not send:
  [stopping-and-skipping.md](stopping-and-skipping.md)

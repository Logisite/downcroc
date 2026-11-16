---
title: Everything a file can say
commands: [batch.submit, batch.preview, batch.validate]
concepts: [batch, job]
screens: []
---

# Everything a file can say

The smallest file gives a send a name and a message. A larger file can say
much more: which mailbox should send it, whether it needs your approval, when
it may go out, and what should happen if nobody replies. All of that lives in
one place, in the same shape, so you can read the file from top to bottom and
know exactly what you are asking downcroc to do.

This page walks that shape block by block. You do not need every block for
every send. The point is to see what each part means, so when you need one of
them you recognise where it belongs.

## The frame

Every campaign file starts the same way:

```json
{
  "schema": "downcroc.campaign/v1",
  "producer": { "name": "my-notes", "version": "1" },
  "campaign": { ... },
  "messages": [ ... ],
  "followups": [ ... ]
}
```

`schema` names the format of the file. `producer` is optional; it records what
created the file, which can be useful when files come from a tool or a script.
The three blocks that matter most are `campaign`, `messages`, and `followups`,
and each one answers a different question.

## The campaign: what this send is and how it behaves

The `campaign` block gives the work its identity and its rules.

```json
"campaign": {
  "name": "Spring outreach",
  "routing": {
    "mode": "auto"
  },
  "options": {
    "approval": "review",
    "suppress_replies": true,
    "reply_window_days": 60,
    "stop_on": ["reply", "bounce"]
  }
}
```

`name` identifies the send, the same way it did in the smallest file. If you
want a specific identifier to refer to later, you can give the campaign a
`key` as well; if you leave it out, downcroc derives one from the file's
name. `routing`
decides which mailbox sends the messages. With `"mode": "auto"`
downcroc chooses for you from the mailboxes that can send; with a fixed mode
you name the account yourself. The idea is simple: either you care which
address it comes from, or you let the daemon spread the work.

`options` describes how the send should behave. `approval` set to `"review"`
means downcroc will wait for you to look it over before anything leaves, while
`"auto"` lets it proceed once it is ready. `suppress_replies` and
`reply_window_days` control whether a later reply should keep follow-ups from
going out, and `stop_on` lists the events that should stop further messages in
a thread, such as a reply or a bounce. You can also set `not_before` to hold
the send until a time you choose, and `allow_duplicates` when sending the same
address again is intentional.

You do not have to spell all of this out. Anything you leave out falls back to
a sensible default; you only write the choices you want to make.

## The messages: who receives what

The `messages` list is the heart of the file. Each entry becomes one [[job]].

```json
"messages": [
  {
    "to": { "email": "ana@example.com", "name": "Ana" },
    "subject": "A quick question",
    "text": "Hi Ana,\n\nDo you have a moment this week?\n",
    "reply_to": "team@example.com"
  },
  {
    "to": { "email": "bo@example.com" },
    "subject": "A quick question",
    "text": "Hi Bo,\n\nDo you have a moment this week?\n"
  }
]
```

Every message needs someone to receive it and something to say. `to` holds the
address and, if you have it, the person's name. `subject` and `text` carry the
message itself; you can include `html` alongside `text` when you want a
formatted version. You can give a message a `key` when you need a stable name
to refer to it later, but if you leave it out downcroc names them in order as
`m1`, `m2`, and so on.

Some fields are there for when you need them: `reply_to` directs answers to a
different address, and `attachments` adds files. One thing you do not put on a
single message is which account sends it; that choice belongs to the campaign's
routing, not to the individual message.

## The follow-ups: what happens later

A follow-up is a message that goes out after some time, usually only if nobody
replied. In a campaign file you describe planned steps in the `followups` block.

```json
"followups": [
  {
    "key": "nudge",
    "after_days": 3,
    "when": "no_reply",
    "subject": "Following up",
    "text": "Hi again,\n\nJust checking in on my note.\n",
    "require_approval": false
  }
]
```

Each step needs a `key` (its name). `after_days` (1–365) says how long to wait,
and `when` says the condition: `no_reply` means send only if the thread stayed
quiet; `always` means send when due regardless of a reply. A step must include
`text` or `html` (or both); `subject` is optional — if you leave it out, the
follow-up replies with the original subject in reply form. `require_approval`
lets you ask for a human check before that later message goes out.

You can also tailor a step for a specific person inside a message. Under that
message, add a `followups` object keyed by the step key and set only what should
change (or `skip` that step for them):

```json
{
  "key": "m1",
  "to": { "email": "ana@example.com", "name": "Ana" },
  "subject": "A quick question",
  "text": "Hi Ana,\n\nDo you have a moment this week?\n",
  "followups": {
    "nudge": { "skip": false, "subject": "Checking in, Ana" }
  }
}
```

An override must refer to a step key that exists in the campaign `followups`. A
file with no follow-ups can leave the block out or keep it empty.

These blocks tell one complete story in the file: a named send, with rules,
messages, and a planned sequence. Follow-ups can also be added or changed later
on an existing [[batch]] as declarations (shared or payload-backed); Part II
explains those forms and their rules.

Taken together, this is the campaign JSON shape downcroc reads. When you need
every field, allowed value, and constraint, Part II has the full contract and the
`batch schema` command prints it from your installed version.

⤷ the full campaign JSON contract (fields, routing/options, follow-ups, CSV/templates):
  [../part-ii/08-batch/prepare.md](../part-ii/08-batch/prepare.md)
⤷ declaring and managing follow-ups in depth (inline vs retroactive, shared/payload):
  [../part-ii/08-batch/followups.md](../part-ii/08-batch/followups.md)

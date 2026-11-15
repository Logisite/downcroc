---
title: The smallest file you can send
commands: [batch.submit, batch.preview, batch.validate]
concepts: [batch, job]
screens: []
---

# The smallest file you can send

When you have more than one message, or you want to give a send a name you can
recognise later, you put the work in a file and hand that file to downcroc.
The smallest useful file is not just a loose list of messages. It is a small,
named campaign: enough structure that downcroc knows what to call it and
enough content to know who to write to.

## A file with a name

Here is a complete file that does exactly that:

```json
{
  "schema": "downcroc.campaign/v1",
  "campaign": {
    "name": "Morning note"
  },
  "messages": [
    {
      "to": { "email": "ana@example.com", "name": "Ana" },
      "subject": "A quick hello",
      "text": "Hi Ana,\n\nJust saying hello.\n"
    }
  ]
}
```

Read it from the top. The first line tells downcroc which kind of file this is.
The `campaign` block gives the work an identity. The `name` is the one you
will recognise later, the label that tells you which send this was when you
look it up again. If you want a specific identifier to refer to, you can add
a `key` yourself; if you leave it out, downcroc derives one for the campaign
from the file's name, so it always has something stable to point to.

Inside `messages` lives the actual work: the person it is for, a subject, and
the text of the note. One message is enough to make the file real; more
messages sit in the same list, each with its own details. You can give a
message a `key` when you need a name you control, and if you do not, downcroc
names them in order: `m1`, `m2`, and so on.

## What this file does not say yet

This smallest file leaves a lot unsaid, and that is fine. It does not choose a
mailbox, it does not set a schedule, and it does not ask for approval in any
special way. downcroc fills in sensible defaults so you can start with the
shape of the message and add choices only when you need them.

When you are ready to see what downcroc makes of it, you can preview or
validate the file before anything is sent. When it reads the way you expect,
you submit it and it becomes a [[batch]] of jobs you can review and send.

⤷ every field this file can carry, explained one block at a time:
  [the-maximal-file.md](the-maximal-file.md)
⤷ validating, previewing, and submitting a file:
  [../part-ii/08-batch/submit.md](../part-ii/08-batch/submit.md)

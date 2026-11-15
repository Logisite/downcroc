---
title: Each person, their own words
commands: [batch.preview, template]
concepts: [template, batch]
screens: []
---

# Each person, their own words

A message lands better when it sounds like it was written for the person
reading it. downcroc lets you write one message in shape and fill in the
details for each person, so you can be personal without copying and pasting
yourself into mistakes.

## Placeholders in your message

Where a detail changes from person to person, you put a placeholder in the
text. A placeholder is a name wrapped in double braces, like `{{name}}` or
`{{company}}`. When downcroc prepares the message for someone, it replaces
that name with that person's value.

In a campaign file you can give each message its own wording, but placeholders
become especially useful when many people share the same message. You write
the sentence once, and the parts that differ come from the data you provide.

## Where the values come from

When you send from a CSV file with a [[template]], each column in the file
becomes a value you can use by name, and downcroc also provides a few helpful
ones such as the person's email address and the name of the batch. If a
placeholder has no value, downcroc tells you, because a message full of blank
gaps is worse than a message that never went out.

## Seeing the result before you send

Because the final words depend on the data, it helps to look at them before
they leave. **batch preview** shows sample messages as they will be sent, with
the placeholders filled in. Reading a preview is how you catch a missing name
or a sentence that sounded fine in the abstract but strange with real details
in it.

⤷ sending to many people from a spreadsheet with a template:
  [csv-and-spreadsheets.md](csv-and-spreadsheets.md)
⤷ previewing and checking work before it goes out:
  [preview-and-test.md](preview-and-test.md)

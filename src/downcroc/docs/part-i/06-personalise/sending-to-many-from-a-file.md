---
title: Sending to many from a file
commands: [batch.submit, batch.preview]
concepts: [batch, template]
screens: []
---

# Sending to many from a file

Writing one message at a time is fine for a handful of people. When the list
grows, you want a way to describe the message once and let downcroc apply it
to everyone in the file. That is what sending from a CSV with a template is
for.

## The list and the letter

The CSV file is the list: each row is a person, and the columns hold the
details about them, starting with their email address. The [[template]] is the
letter: it holds the subject and the body, with placeholders where each
person's details should appear. When you submit the batch, downcroc pairs the
two, filling the letter for every row in the list.

You tell downcroc which file and which template to use when you submit. It
reads the rows, builds a message for each person, and shows you what it is
about to create before anything is sent.

## A path that stays understandable

This kind of send can feel more mechanical than writing a single note, which is
why previewing matters. Before you submit for real, you can preview the batch
to see how the template reads with actual rows, and you can do a dry run to
understand the work without committing to it.

The list gives you reach, and the template gives you consistency. Together they
let you write to many people at once while still speaking to each of them by
name.

⤷ shaping the spreadsheet and the template it uses:
  [csv-and-spreadsheets.md](csv-and-spreadsheets.md)
⤷ checking the result before you send:
  [preview-and-test.md](preview-and-test.md)

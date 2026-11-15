---
title: CSV and spreadsheets
commands: [batch.example, template.new, batch.validate]
concepts: [template, batch]
screens: []
---

# CSV and spreadsheets

A spreadsheet is often the most natural place to keep a list of people. You can
send from that list by saving it as a CSV file and pairing it with a template
that knows how to turn each row into a message.

## What the file needs

The CSV needs a header row so downcroc can tell which column is which. One of
those columns must be the email address for each person. The other columns can
hold anything you want to mention in the message, such as a name or a company,
and you will refer to them by those column names.

Each row becomes one message. downcroc reads the file, checks that the rows
make sense, and reports problems it finds, such as a missing email column or a
row that cannot be turned into a message.

## The template beside it

A template lives in its own folder and holds the pieces of the message: a
`template.toml` with the subject and settings, and a `body.txt` with the text
you want to send. Where the message should include a value from the
spreadsheet, you write a placeholder like `{{name}}`. downcroc fills those
placeholders from the columns in each row.

If you want a starting point, **batch example** can show you example files,
including a CSV and a template, and **template new** can create a template
skeleton for you to fill in. You can also **validate** a file before you send
to be sure downcroc can read it the way you expect.

⤷ making each message personal with placeholders:
  [each-person-their-own-words.md](each-person-their-own-words.md)
⤷ the full template and CSV contract:
  [../part-ii/14-template/template.md](../part-ii/14-template/template.md)

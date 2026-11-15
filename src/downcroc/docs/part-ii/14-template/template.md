---
title: template
commands: [template, template.list, template.new, template.show, template.validate]
flags: []
concepts: [template]
screens: []
---

# template

Templates define reusable message content for CSV-driven sends: a subject, body text (and optional HTML), defaults, reply-to, and attachments. `template` lets you list, create, inspect, and validate templates stored in the templates directory.

Templates are used when sending from a CSV (see `downcroc send` and `downcroc batch prepare|submit` with `--template`).

## Usage

```text
downcroc template <action> [name]
```

Actions: `list`, `new`, `show`, `validate`. If no action is given in an interactive session, a template menu may be offered; otherwise `list` is shown.

## Actions

### list

Lists available templates.

```text
downcroc template list
```

- Scans the templates directory for template folders containing `template.toml` and loads each one.
- For each valid template it reports the name, subject, template variables found in subject/text/html, defaults, and number of attachments. Templates that cannot be loaded are reported as broken with their error.
- If there are no templates, it reports that and suggests creating one.

**Output**

- Default: a table of templates (and any broken templates with errors), and the templates path. Exit status is non-zero if any template is broken.
- With `--json`: prints `{"templates": [...], "broken": [...]}`.

### new

Creates a template skeleton.

```text
downcroc template new <name>
```

- Creates a new template directory named `<name>` containing a starter `template.toml` and `body.txt`.
- Fails if a template with that name already exists.
- The starter manifest sets a subject and reply-to placeholder and includes a `[defaults]` section; the starter body shows how to use variables like `{{ name }}` and `{{ company }}`.

**Output**

- Default: reports the created template name/path and the manifest/body file paths, and suggests editing and validating it.
- With `--json`: prints the template name and path.

### show

Shows a template’s contents.

```text
downcroc template show <name>
```

- Loads and displays the template: name, subject, reply-to, defaults, the text body, and (if present) an indication of HTML content and any attachments.

**Output**

- Default: prints template fields and the body text (and attachment paths when present).
- With `--json`: prints the template as JSON (name, subject, text, html, defaults, reply_to, attachments).

### validate

Validates a template.

```text
downcroc template validate <name>
```

- Loads the template and checks that it is valid. On load/validation failure it reports the error (and hint when available).
- When valid, it reports the template’s variables (from subject/text/html), its defaults, and which CSV columns are needed: `email` plus any variables not covered by defaults (case-insensitively).

**Output**

- Default: on success prints template details and “template is valid”; on failure prints the error/hint. Exit status is `0` when valid, `1` when invalid.
- With `--json`: on success prints `ok`, name, variables, defaults, `needs_columns`, and attachments; on failure prints `ok: false` with the error.

## Template shape (starter)

A new template includes:
- `template.toml` with `subject`, `reply_to`, and a `[defaults]` table.
- `body.txt` with the plain-text body; variables use `{{ name }}`-style placeholders.

Variables used in the subject/body that are not provided by defaults must be supplied as CSV columns when sending.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc template list` — list templates.
- `downcroc template new intro` — create a new template skeleton.
- `downcroc template show intro` — view a template.
- `downcroc template validate intro` — check a template and see required CSV columns.

## See also

- [../08-batch/prepare.md](../08-batch/prepare.md) — validate and preview CSV inputs with a template
- [../12-send/send.md](../12-send/send.md) — guided send (can select/create a template for CSV)
- [../part-i/06-personalise/write-a-template.md](../part-i/06-personalise/write-a-template.md) — writing a template
- [../part-i/06-personalise/csv-and-spreadsheets.md](../part-i/06-personalise/csv-and-spreadsheets.md) — CSV and spreadsheet inputs

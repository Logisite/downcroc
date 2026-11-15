# 17 - The three-part book and the drift guard

The book has three parts with different jobs, plus a tooling layer that keeps
the book true to the CLI. Part I's voice is specified in `16-part-i-the-craft.md`.
Rendering is specified in `15-docs-book.md`. This plan owns the structure, the
complementarity rules, and the checking tool.

## The three parts

```text
Part I  The Craft     read once, in order; questions and stories; thin pages
Part II The Commands  looked up, not read through; the complete contract of
                      every command, subcommand, flag, and error
Part III The Machine  why it behaves as it does; states, pipeline, failures,
                      safety, cookbook, troubleshooting, glossary
```

A reader who finishes Part I can use the CLI for real work. A reader who
consults Part II is exact. Part III explains the behaviour both parts rely on.

### Part I

Twenty-nine pages in six folders: starting, first mail, keeping it running,
mailboxes, follow ups, personalise. Full page list and voice in
`16-part-i-the-craft.md`.

### Part II

One chapter per top-level command group; only `batch` splits, by workflow,
never alphabetically. Part II is nested like Part I: `part-ii/NN-group/`
folders per top-level group, with descriptive page names inside. Every
chapter opens with the `cli_tree.py` render of its command and must cover
every flag and positional that render shows. Structure tracks top-level CLI
groups and batch workflows (grounded in `cli_tree.py`), not the full
subcommand tree.

```text
part-ii/
  01-service/   service.md, serve.md
  02-status/    status.md
  03-init/      init.md
  04-vault/     vault.md
  05-auth/      auth.md
  06-provider/  provider.md
  07-account/   account.md
  08-batch/     prepare.md, submit.md, inspect.md, approve.md,
                holds.md, reassign.md, followups.md
  09-job/       job.md
  10-failed/    failed.md
  11-sending/   sending.md
  12-send/      send.md
  13-review/    review.md
  14-template/  template.md
  15-mail/      mail.md
  16-doctor/    doctor.md
  17-config/    config.md
  18-stats/     stats.md
  19-logs/      logs.md
  20-backup/    backup.md
  21-restore/   restore.md
  22-docs-help/ docs-help.md
  23-openapi/   openapi.md
  24-update/    update.md
  25-uninstall/ uninstall.md
```

`status` is its own chapter (a read of the whole system) separate from
`service` (process control) and `serve` (foreground run). `failed` and `job`
are top-level command groups, not batch subsections. `help` is covered with
`docs` in `22-docs-help/docs-help.md` as a resolver over the same tree and
docs. `batch` is the only split, by workflow against its real subcommands.

Slots/chapters exist as declared paths from the moment Part I names them;
Part II fills named slots, never invented separately. Legacy numeric slot ids
remain aliased in `part-ii/_stubs.txt` for pointer compatibility.

### Part II is written to be read through

"Looked up" is how Part II gets used; it is not how it gets written. Each
chapter is composed so a person can read it start to finish like any other
part of the book, and separately land on it from search or a deep link.

- The chapter opens with a short narrative section in the book's voice: what
  this command is for, when you reach for it, the one idea behind it. Tables
  never open a chapter; prose does.
- Every flag and subcommand entry leads with one plain sentence before any
  exact detail: `--include-failed: also move failed jobs, not just queued
  ones. Use it when a mailbox died with work still waiting.`
- Subcommand sections read as small stories (purpose, the move, the reading,
  what goes wrong), not as fragments. Tables appear inside them as summary,
  never as the whole content.
- Cross-references are written into the flow ("this pairs with X, because
  Y"), so a linear reader builds one connected model instead of visiting
  islands.
- The state, error, and edge material follows the same plain rules as Part I:
  means/do-this pairs, cause and consequence, the reader's next move.
- The lookup aids are layered on top, not instead: the `cli_tree.py` render
  at the top, a short anchor per subcommand and flag, and the complete table
  of error codes at the end.

The test: reading `09-job/job.md` straight through leaves a person fluent in
jobs; searching it answers one question without reading anything else.

### Part II formatting

- Do not use tables for branching or conditional surfaces. Describe
  subcommands/actions and any flags whose meaning or availability depends on
  the action or context in prose and sections (per action or subcommand), so
  each can carry its purpose, behavior, effects, prerequisites, output, and
  notes in full.
- Use tables only for simple, flat lists of leaf items: end flags, or end
  commands that take no further flags or subcommands. Prefer prose and lists
  elsewhere so the contract stays readable and rich enough to scrape detail
  from.

### Part III

```text
30-pipeline.md           34-safety.md
31-seats-and-threads.md  35-cookbook.md
32-failures.md           36-troubleshooting.md
33-states.md             37-glossary.md
```

`33-states.md` is the single source of truth for status words. `37-glossary.md`
is the single source of truth for mechanic words.

## Complementarity rules

Part I and Part II must not duplicate each other. The rules that make the
overlap near zero by construction:

1. **The split**: Part I holds questions, stories, output reading, and at most
   two first-session failure modes. Part II holds completeness and exactness.
2. **The flag ceiling**: Part I shows only the 2-3 flags its story needs. The
   complete flag set lives only in Part II.
3. **The failure rule**: Part I shows only failure modes a normal user hits in
   the story's first session. Complete error-code tables live only in Part II.
4. **The anchors**: Part I ends each lean with a pointer line to the Part II
   slot; Part II opens with one back-anchor sentence to the Part I page that
   introduced the command. These two sentences are the only repeated text.
5. **The glossary**: every mechanic word is defined once in `37-glossary.md`
   and linked everywhere else. A term may not appear in any page unless the
   glossary has it. Entries are written from the reader's question, not the
   mechanism; an entry that can only be written in mechanism words marks a
   term that must not appear in Part I.

## Page frontmatter for the drift guard

Every book page declares what it touches, using command ids from the real
parser tree (the same tree `scripts/cli_tree.py` walks):

```yaml
---
title: Who sent this email?
commands: [job.show, job.attempts]
flags: [job.show --addresses]
concepts: [sender-policy, send-attempt]
---
```

## scripts/docs_map.py

Three commands, all built on two structured sources: the parser tree from
`build_parser()` and the frontmatter of the book.

```sh
uv run python scripts/docs_map.py check
```

Coverage and lint in one pass:

- every command, subcommand, flag, and positional in the parser tree must be
  claimed by at least one page's frontmatter, or appear in a Part II stub
- no page may claim a command or flag the tree no longer has
- every Part I pointer line must resolve to a real page or a declared stub
- every `[[term]]` must exist in `37-glossary.md`
- Part I page caps: at most 3 flags shown, no error-code tables

```sh
uv run python scripts/docs_map.py touched src/downcroc/cli/parser/batch.py
```

Maps source files to commands to pages: the maintainer learns which pages a
change affects without reading the diff semantically.

```sh
uv run python scripts/docs_map.py diff HEAD~1
```

`git diff --name-only` fed into the same mapping, so after a commit the
workflow is: diff, edit the listed pages, run `check` green before pushing.

The check is a release gate like `uv lock --check`: a green book matches the
CLI.

## Authoring order

1. Part I per `16`: `02/one-email.md` as template page, then gmail, daily
   round, the file-format pair, the rest.
2. Glossary grows continuously alongside Part I.
3. Part II fills the slots Part I named, each chapter opened with its
   `cli_tree.py` render.
4. Part III last: states and glossary stabilize once both parts exist.
5. `docs_map.py check` after the first ten pages, `touched`/`diff` when the
   mapping has real frontmatter to chew on.

## Relationship to existing plans

- `15` owns the renderer, schema, frontmatter keys, packaging, and tests. The
  `commands`/`flags`/`concepts` frontmatter keys extend that schema.
- `16` owns Part I's voice, page skeleton, and folder list.
- `12-module-map.md` and `02-api-contract.md` remain the engineering truth;
  this plan never restates their content, it links to it.

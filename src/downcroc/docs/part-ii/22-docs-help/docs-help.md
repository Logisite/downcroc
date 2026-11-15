---
title: docs and help
commands: [docs, help]
flags: [--list, --search, --raw, --open, --width, docs topic, help topic]
concepts: []
screens: []
---

# docs and help

`docs` opens and reads the downcroc documentation book. `help` shows command help and topic guides. Use `docs` for the book (concepts, how-tos, and reference chapters) and `help` for CLI usage and quick topic explanations.

## docs

Reads the documentation book.

### Usage

```text
downcroc docs [topic] [--list] [--search QUERY] [--raw] [--open] [--width WIDTH]
```

- `topic` is a page path, slug, or title (for example a chapter path or name). With no topic or search/list flags, `docs` opens the interactive reader on a terminal, or shows the index in non-interactive contexts.

### Behavior

- `--list` lists every page (with title, section, summary/tags). With `--json`, prints the page list as JSON.
- `--search QUERY` searches titles, tags, and body and prints matching pages (and matching lines/snippets). With `--json`, prints hits; exits non-zero if there are no matches.
- `--raw` prints the exact Markdown of the selected page to stdout.
- `--open` opens the selected page in a browser.
- Without those flags, the selected topic (defaulting to the index when appropriate) is rendered to the terminal. `--width WIDTH` wraps the page at the given number of terminal columns (otherwise it fits the terminal up to a reasonable width). On a TTY (and when not JSON/no-pager), output may be shown in a pager.

If the documentation book is not installed, `docs` fails with a “docs missing” error. Ambiguous topics list matching choices; an unknown topic suggests listing or searching.

### Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

### Examples

- `downcroc docs` — open the interactive docs reader (terminal) or the index.
- `downcroc docs --list` — list every page.
- `downcroc docs --search "follow-ups"` — search the book.
- `downcroc docs part-ii/08-batch/submit` — read a specific page.
- `downcroc docs part-i/01-starting/before-you-begin --raw` — print a page’s Markdown.
- `downcroc docs --open part-iii/33-states` — open a page in a browser.

## help

Shows help for a command or topic.

### Usage

```text
downcroc help [topic]
```

- With no `topic`, prints the top-level CLI help/overview and the list of available help topics.
- With a `topic`, prints help for that topic. If the topic names a command, it shows that command’s `--help`. If it is a known help topic, it shows the topic text. An unknown topic prints the topic index and exits with a non-zero status.

Help topics provide short explanations (for example concepts and common tasks) alongside command usage.

### Examples

- `downcroc help` — show CLI overview and topics.
- `downcroc help batch` — show help for the `batch` command.
- `downcroc help send` — show help for `send`.

## See also

- [../23-openapi/openapi.md](../23-openapi/openapi.md) — export the API specification
- [../part-i](../part-i) — Part I: The Craft
- [../part-iii](../part-iii) — Part III: The Machine

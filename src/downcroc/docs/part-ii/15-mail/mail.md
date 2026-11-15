---
title: mail
commands: [mail, mail.list, mail.show, mail.threads, mail.thread, mail.attachment, mail.prune]
flags: [mail.attachment -o, mail.list --account, mail.prune --account, mail.threads --account, mail.threads --batch, mail.prune --dry-run, mail.list --folder, mail.attachment --force, mail.list --limit, mail.threads --limit, mail.list --offset, mail.threads --offset, mail.list --reply-state, mail.list --since, mail.list --thread, mail.list --until]
concepts: []
screens: []
---

# mail

`mail` lets you browse and manage ingested mail: list messages, view a message or a thread, save attachments, and prune inbox copies of mail sent by your own accounts. This operates on mail stored by downcroc (for example in INBOX) and the reply/thread state it has derived.

## Usage

```text
downcroc mail <action> [options]
```

Actions: `list` (default), `show`, `threads`, `thread`, `attachment`, `prune`. In an interactive session with no action, a mail menu may be offered.

## Actions

### list

Lists messages.

```text
downcroc mail list [--account ACCOUNT] [--folder {INBOX}] [--thread THREAD]
                  [--reply-state {confirmed,probable,late,bounced}]
                  [--since SINCE] [--until UNTIL] [--limit LIMIT] [--offset OFFSET]
```

- Filters: `--account` by account, `--folder` (INBOX), `--thread` by thread id, `--reply-state` by reply classification, `--since`/`--until` by date (`YYYY-MM-DD`).
- Paging: `--limit` (1–500, default 100) and `--offset`.

**Output:** a table of date, from, subject, reply state, attachment count, and message id (plus a page footer when paged). Reply-state labels are explained once per run when present: “confirmed reply” (headers prove it answers a job), “likely reply” (subject/participant match without proving headers), “late reply” (after the reply window), “bounce” (delivery failure). With `--json`, prints the messages.

### show

Shows one message.

```text
downcroc mail show <message_id>
```

- Displays message details: id, account, folder, uid, message-id, from, to, subject, date, reply state, thread, job, whether it is a DSN/bounce, and attachments (id, filename, size). Prints the text body (noting if truncated) or “(no text body)”.

With `--json`, prints the message as JSON.

### threads

Lists threads.

```text
downcroc mail threads [--account ACCOUNT] [--batch BATCH] [--limit LIMIT] [--offset OFFSET]
```

- Filters: `--account`, `--batch`. Paging: `--limit` (1–500, default 100), `--offset`.

**Output:** a table of thread id, subject, message count, reply count, and last seen (with page footer when paged). With `--json`, prints threads.

### thread

Shows one thread and its messages.

```text
downcroc mail thread <thread_id>
```

- Displays thread details (id, subject, batch, message/reply counts, first/last seen) followed by the thread’s messages with reply-state explanations when present.

With `--json`, prints the thread detail and messages as JSON.

### attachment

Saves an attachment to disk.

```text
downcroc mail attachment <attachment_id> [--output PATH] [--force]
```

- Downloads the attachment and writes it to `--output` or, if omitted, to a file named from the attachment in the current directory. If `--output` is a directory (or ends with a path separator), the attachment filename is used inside it.
- If the destination file already exists, `--force` overwrites it; otherwise confirmation/overwrite rules apply.

**Output:** reports the written path and byte count (or JSON with path/bytes).

### prune

Removes inbox copies of mail sent by your own accounts.

```text
downcroc mail prune [--account ACCOUNT] [--dry-run] [--yes]
```

- Targets messages in the inbox that were sent by your own accounts. `--account` limits pruning to one account.
- `--dry-run` reports how many messages and bytes would be removed without deleting anything.
- Without `--dry-run`, asks for confirmation (unless `--yes` is given) before removing messages.

**Output:** reports how many messages (and bytes) would be or were removed. If activity counters could not be rebuilt after a real prune, it suggests running `downcroc stats rebuild`. With `--json`, prints the prune result.

## Reply states

Messages can be classified by how they relate to sent jobs: `confirmed` (headers prove it answers a job), `probable` (likely reply by subject/participant match), `late` (arrived after the reply window), or `bounced` (a delivery failure, not a person). These appear in message listings/details and can be filtered with `--reply-state`.

## Common flags

`--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc mail list` — list recent ingested messages.
- `downcroc mail list --reply-state confirmed` — list confirmed replies.
- `downcroc mail show <message_id>` — view a message.
- `downcroc mail threads --batch bat_123` — list threads for a batch.
- `downcroc mail thread <thread_id>` — view a thread and its messages.
- `downcroc mail attachment <attachment_id> --output ./downloads/` — save an attachment.
- `downcroc mail prune --dry-run` — preview removing self-sent inbox copies.

## See also

- [../18-stats/stats.md](../18-stats/stats.md) — rebuild/prune activity statistics
- [../19-logs/events/inbound-watcher.md](../19-logs/events/inbound-watcher.md) — inbound/watcher log events
- [../part-i/03-keeping-it-running/where-is-my-stuff.md](../part-i/03-keeping-it-running/where-is-my-stuff.md) — where data and logs live
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md) — how inbound mail and replies fit in

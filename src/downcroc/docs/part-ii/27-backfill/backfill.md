---
title: backfill
commands: [backfill, backfill.status, backfill.explain, backfill.retry]
flags: [backfill.explain attempt_id, backfill.retry attempt_id]
concepts: [backfill]
screens: []
---

# backfill

`downcroc backfill` shows the holes left in older sent mail where downcroc did
not record a conversation id. It also lets you put one hole back in the next
pass after you have fixed the reason it could not be checked.

This command reads the daemon's stored state. It never runs a search itself and
never changes a sent message.

## Usage

```text
downcroc backfill status
downcroc backfill explain ATTEMPT_ID
downcroc backfill retry ATTEMPT_ID
```

## Actions

### status

`status` lists the holes for each account and why each account cannot make
progress. The columns are:

- `due`: holes the next pass will check.
- `waiting`: holes with a scheduled next check.
- `missing`: holes the provider confirmed absent.
- `unresolved`: holes downcroc could not check after repeated errors.
- `open`: due plus waiting, the holes still in play.
- `total`: open plus the two terminal states.
- `blocked`: why this account is not being drained, such as `needs_reauth`.

A hole with a null next check is due, including holes written by an older
version of downcroc. They are picked up on the first pass after the upgrade.

### explain

`explain` takes a send attempt id and reports what the last check saw: the
search scope, the number of results, the stored thread id, the next check time,
and the account state. Use the attempt id from a `backfill.missing` or
`backfill.unresolved` log line.

### retry

`retry` puts one hole back in the next pass. It is the human override for a
hole you believe is still there, for example after you reconnect an account or
move a message back into Sent. It does not resend mail. In a script, pass
`--yes`.

## Output

- Default: human-readable records and a table.
- `--json`: the full records, one object per response.

## Examples

- `downcroc backfill status` - show every account's holes.
- `downcroc backfill explain att_676d9af7edb4feb0` - explain one hole.
- `downcroc backfill retry att_676d9af7edb4feb0 --yes` - recheck one hole.

## See also

- [backfill log events](../19-logs/events/backfill.md) - what each check writes.
- [../19-logs/command.md](../19-logs/command.md) - querying the log.
- [../07-account/account.md](../07-account/account.md) - reconnecting a mailbox.

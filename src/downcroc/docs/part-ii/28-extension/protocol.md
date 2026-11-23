---
title: Extension wire protocol
commands: []
flags: []
concepts: []
screens: []
---

# Extension wire protocol

This page defines the exact bytes between downcroc and an extension. An
extension does not import downcroc modules. It reads newline-delimited JSON from
standard input and writes newline-delimited JSON to standard output.

Every frame is one JSON object on one line. No other output is protocol. Raw
text on stdout or stderr is ignored by the broker and, for stdout, can make the
extension look broken.

## Frame order

1. downcroc sends `hello` once when the process starts.
2. downcroc sends an `event` frame for each subscribed event.
3. The extension sends an `actions` frame with zero or more capability calls.
4. downcroc executes the actions in order and sends one `result` frame.
5. Steps 2 to 4 repeat.
6. downcroc closes stdin when the extension is disabled or the daemon stops.

The same loop is used by `extension test`, with one event and then shutdown.

## hello

```json
{
  "type": "hello",
  "extension": "reply-bot",
  "tier": "standard",
  "capabilities": ["log", "mail.reply"],
  "settings": {"tone": "brief"},
  "artifact": "artifacts/reply-bot-1.0.0.pyz"
}
```

`artifact` is present only for a `.pyz` artifact. `settings` comes from
`[extensions.reply_bot].settings` in config and never contains secrets.

## event

```json
{
  "type": "event",
  "event": "reply.attributed",
  "payload": {
    "event": "reply.attributed",
    "id": "evt_1",
    "message": "msg_1",
    "account": "acct_1",
    "reply_state": "confirmed",
    "subject": "Re: Hello"
  }
}
```

The payload is sanitized with an allowlist. A field survives only if it is in
this exact list:

`event`, `id`, `account`, `account_id`, `message`, `message_id`, `job`,
`job_id`, `batch`, `batch_id`, `thread`, `thread_id`, `reply_state`, `subject`,
`from`, `transport`, `state`, `created_at`, `sent_at`, `received_at`, `reason`.

The `event` key is always present inside `payload`, even if the source event had
no other fields. Every other field is omitted when the source event does not
carry it. Always check before using it.

Quota and counter fields are **not** in event payloads. `used`, `reserved`,
`remaining`, `available`, `quota_limit`, and similar values never reach an
extension through an event. If you need them, call `quota.get` for a single
account or `stats.query` with `kind = "accounts"` for per-account used,
reserved, and available counts. Both are standard capabilities.

No password, token, vault path, raw credential, body text, or header value is
included in an event payload. An extension that needs message content calls
`message.get`, which returns the sanitized message record.

## actions

```json
{
  "actions": [
    {"capability": "kv.get", "params": {"key": "handled:msg_1"}},
    {"capability": "log", "params": {"level": "info", "message": "seen"}}
  ]
}
```

`capability` is required. `params` is a JSON object. The old flat form where
parameters sit next to `capability` is accepted, but new extensions should use
`params` because it is unambiguous.

An empty action list is valid. It tells downcroc you chose to do nothing.

## result

```json
{
  "type": "result",
  "results": [
    {"ok": true, "value": null},
    {"ok": true, "value": {"ok": true}}
  ]
}
```

The result at index `n` belongs to the action at index `n`. A failed call looks
like this:

```json
{"ok": false, "error": "CapabilityDenied", "detail": "capability not granted"}
```

Common errors are `CapabilityDenied`, `ValueError`, `ExtensionTimeout`, and
`ExtensionCrashed`. Treat all of them as "the action did not happen".

## error frames

downcroc may send an error frame instead of a result:

```json
{"type": "error", "error": "protocol", "detail": "invalid json from extension"}
```

An error frame means the conversation is over. Do not send more actions. Stop
the process cleanly.

## Timeouts

If no actions frame arrives within `extensions.call_timeout_s`, downcroc logs
`extension.timeout`, stops the process, and restarts it up to
`extensions.max_restarts`. Long network waits belong in `http.request`, which
uses the same timeout but runs in the daemon.

## Standard input and output rules

- Read with `for line in sys.stdin`, not one fixed-size read.
- Write one action frame per event, then keep reading.
- Flush after every write.
- Do not print banners, prompts, or stack traces to stdout.
- stderr is discarded. Put diagnostics in the `log` capability so they appear
  in the daemon log with your extension id.

## Loop example

```python
import json
import sys

for line in sys.stdin:
    try:
        frame = json.loads(line)
    except ValueError:
        continue
    if frame.get("type") != "event":
        continue
    print(
        json.dumps(
            {"actions": [{"capability": "log", "params": {"message": "handled"}}]}
        ),
        flush=True,
    )
```

This is the smallest correct program. Everything else is a decision about
which capabilities to call and what to do with their results.

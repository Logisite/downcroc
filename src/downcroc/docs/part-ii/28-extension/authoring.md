---
title: Writing an extension
commands: []
flags: []
concepts: []
screens: []
---

# Writing an extension

This chapter teaches you to write an extension from an empty directory. It does
not assume you have read the source. When you finish, you will have a single
`.pyz` file that installs with one command and reacts to a reply.

## The idea

An extension is a small program. downcroc starts it as a child process and sends
it JSON lines on standard input. The extension reads those lines, decides what
to do, and writes JSON lines on standard output asking downcroc to perform
capabilities. downcroc never sends a credential to the extension. It performs
the credentialed work itself and returns a result.

That means your code only needs three things:

1. read a line of JSON from `stdin`
2. decide which capabilities to call
3. print a JSON line with the actions and keep reading

## Step 1: make a directory

```sh
mkdir reply-bot
cd reply-bot
```

## Step 2: write the manifest

Create `downcroc-extension.toml`:

```toml
id = "reply-bot"
name = "Reply bot"
version = "1.0.0"
tier = "standard"
events = ["reply.attributed"]
capabilities = ["message.get", "kv.get", "kv.set", "log", "mail.reply"]
```

The fields are:

- `id`: a lowercase id used by the CLI. Letters, digits, `_` and `-` only.
- `name`: a human label.
- `version`: any string. It is used in the artifact filename.
- `tier`: `standard` or `elevated`. Start with `standard`.
- `events`: the daemon events you want to receive. Use real event names such as
  `reply.attributed`, not names you invent.
- `capabilities`: the actions you want to ask for. They are default deny. You
  grant a subset in config later.

A standard manifest cannot request an elevated capability. The daemon refuses
to load it if it does. See [Elevated extensions](elevated.md) for the other
tier.

## Step 3: write __main__.py

Start with the smallest useful program:

```python
import json
import sys

for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    if message.get("type") != "event":
        continue
    print(
        json.dumps(
            {
                "actions": [
                    {
                        "capability": "log",
                        "params": {"level": "info", "message": "saw an event"},
                    }
                ]
            }
        ),
        flush=True,
    )
```

The `flush=True` matters. downcroc is waiting for a line, not for your process
to exit.

The first line downcroc sends is a `hello` frame. This program ignores it. The
next lines are `event` frames. After your actions run, downcroc sends a `result`
frame. Your loop can ignore it too. The exact shapes are in
[Wire protocol](protocol.md).

## Step 4: build one file

```sh
downcroc extension build . --output reply-bot.pyz
```

The command prints the file path and its SHA-256. The `.pyz` contains both your
code and the manifest. One file is all you hand to someone else.

## Step 5: install and enable

```sh
downcroc extension add reply-bot.pyz
downcroc extension enable reply-bot
```

`add` copies the artifact under your config directory, records the checksum,
and reloads the host. It does not enable the extension. `enable` does that.
See [Artifacts](artifacts.md) for verification details.

## Step 6: try it without waiting for mail

```sh
downcroc extension test reply-bot --input '{"event":"reply.attributed","message":"msg_1"}'
```

The command prints one result per action. Then read the log:

```sh
downcroc extension logs reply-bot
```

You should see `extension.call` with capability `log`.

## Step 7: reply to a real reply

Replace `__main__.py` with this complete example:

```python
import json
import sys

for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    if message.get("type") != "event":
        continue

    payload = message.get("payload") or {}
    if payload.get("event") != "reply.attributed":
        continue

    message_id = payload.get("message")
    if not message_id:
        continue

    key = f"handled:{message_id}"
    print(
        json.dumps({"actions": [{"capability": "kv.get", "params": {"key": key}}]}),
        flush=True,
    )
```

The first call only reads state. To use its result, read the `result` frame that
comes back and then send the next action. A complete two-step loop looks like
this:

```python
import json
import sys


def emit(action):
    print(json.dumps({"actions": [action]}), flush=True)


def read_result():
    for line in sys.stdin:
        try:
            frame = json.loads(line)
        except ValueError:
            continue
        if frame.get("type") == "result":
            return frame.get("results") or []
    return []


for line in sys.stdin:
    try:
        frame = json.loads(line)
    except ValueError:
        continue
    if frame.get("type") != "event":
        continue

    payload = frame.get("payload") or {}
    if payload.get("event") != "reply.attributed":
        continue
    message_id = payload.get("message")
    if not message_id:
        continue

    key = f"handled:{message_id}"
    emit({"capability": "kv.get", "params": {"key": key}})
    result = read_result()
    if result and result[0].get("value"):
        continue

    emit(
        {
            "capability": "mail.reply",
            "params": {
                "message": message_id,
                "text": "Thanks, we have noted your reply.",
            },
        }
    )
    read_result()

    emit({"capability": "kv.set", "params": {"key": key, "value": "1"}})
    read_result()
```

This example is complete. It reads the event, checks its own memory, sends a
threaded reply, then records that it handled the message. It needs no source
reading.

## Reading results

Every action produces one result in the same order. A result is either:

```json
{"ok": true, "value": {"ok": true}}
```

or:

```json
{"ok": false, "error": "CapabilityDenied", "detail": "capability not granted"}
```

Never assume a call worked. Check `ok` before acting on `value`.

## Common mistakes

- Printing text that is not JSON. downcroc ignores it and waits until timeout.
- Forgetting `flush=True`. The process waits, downcroc waits, and nothing moves.
- Requesting a capability you did not grant in config. The call returns
  `CapabilityDenied`.
- Subscribing to an event name that does not exist. Use
  `downcroc logs --event` to see real names.
- Using `reply.received`. The real reply event is `reply.attributed`.

## Next

Read [Wire protocol](protocol.md) for the exact frames, then
[Capabilities](capabilities.md) for every call you can make.

from __future__ import annotations

import json
import os
import sys


def emit(action: dict) -> None:
    print(json.dumps({"actions": [action]}), flush=True)


def read_result() -> None:
    for line in sys.stdin:
        try:
            frame = json.loads(line)
        except ValueError:
            continue
        if frame.get("type") == "result":
            return


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if message.get("type") != "event":
            continue
        payload = message.get("payload") or {}
        leaked = [key for key in os.environ if key.startswith("DOWNCROC_")]
        detail = "ENVLEAK" if leaked else "clean"
        if payload.get("reason") == "rounds":
            emit({"capability": "kv.get", "params": {"key": "rounds"}})
            read_result()
            emit({"capability": "log", "params": {"message": "multi-round"}})
            read_result()
            emit({"capability": "kv.set", "params": {"key": "rounds", "value": "1"}})
            read_result()
            continue
        if payload.get("reason") == "quota":
            print(
                json.dumps(
                    {
                        "actions": [
                            {
                                "capability": "quota.get",
                                "params": {"account": payload.get("account", "acct_1")},
                            }
                        ]
                    }
                ),
                flush=True,
            )
            continue
        if payload.get("reason") == "publish":
            print(
                json.dumps(
                    {
                        "actions": [
                            {
                                "capability": "event.publish",
                                "params": {
                                    "event": "quota.committed",
                                    "payload": {
                                        "used": 30,
                                        "limit": 50,
                                        "remaining": 20,
                                    },
                                },
                            }
                        ]
                    }
                ),
                flush=True,
            )
            continue
        if payload.get("reason") == "cli":
            print(
                json.dumps(
                    {
                        "actions": [
                            {
                                "capability": "cli.run",
                                "argv": ["--version"],
                            }
                        ]
                    }
                ),
                flush=True,
            )
            continue
        if payload.get("reason") == "reply":
            print(
                json.dumps(
                    {
                        "actions": [
                            {
                                "capability": "mail.reply",
                                "message": payload.get("message", ""),
                                "text": "Thanks, noted.",
                            }
                        ]
                    }
                ),
                flush=True,
            )
            continue
        actions = [
            {
                "capability": "log",
                "level": "info",
                "message": f"handled:{payload.get('message', '')}",
                "fields": {"env": detail},
            }
        ]
        if payload.get("reason") == "deny":
            actions.append(
                {
                    "capability": "mail.send",
                    "account": "none",
                    "to": "nobody@example.test",
                    "subject": "denied",
                    "text": "denied",
                }
            )
        print(json.dumps({"actions": actions}), flush=True)


if __name__ == "__main__":
    main()

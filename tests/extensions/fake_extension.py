from __future__ import annotations

import json
import os
import sys


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

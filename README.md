# downcroc

Always-on local daemon for personalised mail merged from your own Gmail or IMAP accounts.
Batches in, mail out, replies tracked, statistics kept on this machine.

Requires Python 3.14. Install the wheel into a clean environment and run the
`downcroc` console script:

    python -m pip install downcroc-1.0.0rc1-py3-none-any.whl
    downcroc --version

From a checkout, use uv:

    uv run downcroc service start
    uv run downcroc vault unlock
    uv run downcroc logs --follow
    uv run downcroc service stop

## Common commands

    uv run downcroc account providers
    uv run downcroc account add --provider generic --address you@example.com
    uv run downcroc account connect ACCOUNT_ID
    uv run downcroc account list

    uv run downcroc batch preview campaign.json
    uv run downcroc batch submit campaign.json --approve all
    uv run downcroc batch list
    uv run downcroc job list

    uv run downcroc mail list
    uv run downcroc mail show MESSAGE_ID
    uv run downcroc failed list

    uv run downcroc stats summary
    uv run downcroc config show
    uv run downcroc config set sending.jitter_min 2

    uv run downcroc backup ~/backups/

`vault unlock` and `account connect` prompt for passwords. Add
`--password-stdin` to read one from a pipe. Most read commands accept `--json`.

Human output is colourised only on a terminal. Set `NO_COLOR=1` to turn it off.

Design and decisions live in `plan/`.

## Licence

downcroc is licensed under the Apache License, Version 2.0. See `LICENSE` and
`NOTICE`. Third-party licence information is in `THIRD_PARTY_NOTICES.md` and is
also installed with the package metadata.

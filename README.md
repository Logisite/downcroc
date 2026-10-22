# downcroc

Always-on local daemon for personalised mail merged from your own Gmail or IMAP accounts.
Batches in, mail out, replies tracked, statistics kept on this machine.

Requires Python 3.14 and uv.

    uv run downcroc service start
    uv run downcroc logs --follow
    uv run downcroc service stop

Design and decisions live in `plan/`.

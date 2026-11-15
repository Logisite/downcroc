---
title: The daily round
commands: [status, failed.list]
flags: []
concepts: [status, queue, failed-job, vault]
screens: [status-panel, failed-list]
---

# The daily round

Once downcroc is connected and a first batch has gone out, it mostly runs
itself. Sends go out within the allowance, the watcher keeps an eye on the
inbox, and follow-ups fire when they are supposed to. The work left over is
not operating the daemon. It is looking at it, briefly, on purpose, so that
small problems stay small.

This page is that look. It takes about a minute, and after a week you will do
it without the page.

## Starting the round

The round begins where everything begins: the main menu. Choose **status**.
The screen that opens has no fields to fill, because there is nothing to
configure about looking. Press `r` to run, and read what comes back:

```text
  ┌──────────────────────────────────────────────────────────────┐
  │daemon    running, pid 8842, http://127.0.0.1:8765            │
  │paths     config /home/you/.config/downcroc,                  │
  │          data /home/you/.local/share/downcroc                │
  │log       /home/you/.local/share/downcroc/logs/downcroc.jsonl,│
  │          last write 4m ago                                   │
  │vault     unlocked                                            │
  │sending   running                                             │
  │accounts  3 total                                             │
  │queue     34 sent, 0 failed                                   │
  └──────────────────────────────────────────────────────────────┘
```

Read it as a paragraph, top to bottom. The daemon is running and reachable
only on your own machine, which is where it should be. The vault is
unlocked, which means the daemon can reach the credentials it needs; a clean
stop locks it again, so unlocked is what a working day looks like. **sending
running** means dispatch is allowed to send. Three mailboxes are connected.
And the queue line is the whole morning in two numbers: 34 sent, and a
failed count of zero.

Most days, that failed count is the only number you truly need. The round's
skill is not remembering seven lines. It is noticing the line that does not
say what you expected, and asking one question about it.

> Words this page uses
>
> **queue** is the tally of what has gone out and what could not.
> **vault unlocked** means the daemon can read its stored credentials.
> A stopped daemon leaves the vault locked, and that is normal.

## The same thing, typed

```sh
downcroc status
```

The typed form prints the same lines without the frame. It exists for cron,
for scripts, and for the moment you are outside the interactive session. If
you are inside one, the menu and `r` are fewer keys than any sentence about
it.

## When the failed count is not zero

One morning the last line reads `34 sent, 1 failed`. A failed send is not a
crisis, and it is important not to treat it as one. The daemon already did
the hard part: it recorded what went wrong, kept the job, and will try again
within the rules of the mailbox. Your part is to look, so that a job failing
for a reason nobody notices does not quietly spend all of its retries.

From the main menu choose **failed**, then **list**. The rows come back as a
table:

```text
job          recipient         code                   attempts  failed_at
job_7b21e9   ana@example.com   account_needs_reauth   1         09:04
job_c408aa   sam@example.com   smtp_unavailable       2         09:07
```

Each row gives the job, the recipient, the reason as a short code, how many
attempts it has already spent, and when it last failed. The code is the
whole story compressed to one word, and every code has a plain meaning:

**account_needs_reauth** means the mailbox told the daemon its login stopped
working. Nothing is broken; the mailbox is waiting for a working login. The
fix is a few presses away: choose **account**, pick the mailbox, choose
**connect**. The job kept everything you wrote, so once the mailbox works,
the send resumes where it left off.

**smtp_unavailable** means the receiving mail server could not be reached.
That is a property of the network or of that one server, not of the email
you wrote. The daemon will retry it on its own. You read the row, you
understand it, and you leave it alone.

What not to do in the first minute: nothing here needs to be retried by
hand, cancelled, or forced. Those moves exist, and they are decisions, not
fixes. They have their own page later in this folder.

## Closing the round

The round ends the way it began, with a read rather than a command. Every
line on the status panel either says what you expect or names whose decision
it was: a mailbox you paused, a login that expired, a server that was not
home. Lines you can explain are the day's work done. The one line you cannot
explain is worth chasing before the day starts, and every screen you met on
this page tells you who owns each state.

If the round felt shorter than reading about it, that is how it should feel.
The next page walks one failure from beginning to end, so the first time you
meet a real one it is already familiar.

⤷ every check the status panel can show, and what each state means:
  10a-status.md
⤷ the complete list of failure codes, what each means, and every option on
  the failed screen: 24-failed.md
⤷ the whole story of a login that expired: [gmail.md](../01-starting/gmail.md)

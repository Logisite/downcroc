# 16 - Part I: The Craft

Part I of the docs book teaches a person who has never heard of downcroc how to
run it daily. This plan fixes the voice, the page shape, and the writing order
before any page is written.

It pairs with `15-docs-book.md` (rendering) and the future Part II contract
pages. Part I never duplicates Part II: questions and stories here, complete
contracts there.

## The voice: a companion, not a manual

The book talks like a knowledgeable friend leaning over your shoulder. Rules
that make it so:

- **Address the reader as "you"** and downcroc as "it" or "the daemon".
- **Start every page from the reader's situation**, not from a command:
  "It is Monday morning. You want to mail 40 people."
- **Explain by asking the question the reader would ask**, then answering it:
  "Why did it send from that mailbox? Because it picked the one with the most
  allowance left. That is a good default. Here is how to change it."
- **Admit feelings**: "This looks scary. It is not. Here is what it means."
- **No wall-of-flags.** A page shows the 2 or 3 flags the story needs. The
  complete set lives in Part II, always one pointer line away.
- **Plain words for states and errors.** Every mechanic word is either a
  glossary link or carries its meaning inline the first time:
  "`retry_wait` means the mail server said come back later. You do nothing.
  It retries itself."
- **Honesty as tone.** "downcroc cannot promise 09:00. Nothing real can.
  Here is what it does promise."
- **No "simply", "just", "obviously", "easy".** If a step needs those words,
  the step is explained badly.
- Sentences stay short. Paragraphs are two to four lines. A page is 60 to 120
  lines of source. If a page grows past that, it becomes two pages.

## What it sounds like

Docs-speak (forbidden):

> The `--daily-allowance` parameter configures the per-account daily send
> ceiling. Once the ceiling is reached, dispatch pauses until the next local
> day.

Book-speak (the target):

> Think of the allowance as the number of stamps you give each mailbox per
> day. Give alice 200 and bob 40, and the daemon sends from alice four times
> as often, without you planning anything.
>
> When a mailbox runs out of stamps, it does not error. It waits until
> midnight, your local midnight, and starts again.
> ⤷ every knob on a mailbox, and what it costs you: 12-account.md

The difference is a small story (stamps), a feeling (no error), and a fact
placed where a beginner would meet it (midnight is local, not UTC).

## The page shape

Every Part I page follows this skeleton, in this order:

```text
title          the question, in the reader's words
opening        1-3 sentences placing the reader in a real moment
the move       the one command (plus at most 3 flags), with expected output
the reading    that output explained line by line, in glossary-linked words
the moment     the 1-2 things that go wrong in the first session, each with
               cause, what it looks like, and the fix
terms          all mechanic words resolve to glossary.md or carry an inline
               plain sentence the first time
pointers       inline pointer lines wherever the page leans on a Part II
               fact; targets may be named stubs that do not exist yet
```

Frontmatter declares what the page touches, for the docs mapping tool:

```yaml
---
title: Who sent this email?
commands: [job.show, job.attempts]
concepts: [sender-policy, send-attempt]
---
```

## The folders and pages

```text
01-starting/
  what-is-downcroc.md      the daemon idea in three sentences; what it is not
  turn-it-on.md            serve vs service, the lock, pause/resume, doctor
  first-run.md             init, vault unlock/lock, keyring, auth status
  connect-a-mailbox.md     add/connect/verify, the generic provider
  gmail.md                 OAuth vs app password; publishing the OAuth app so
                           tokens stop expiring weekly; needs_reauth recovery
  where-is-my-stuff.md     the three directories, vault, content store, logs

02-first-mail/
  one-email.md             job create --send end to end
  quick-send.md            send path, review
  the-minimal-file.md      the bare JSON array, 6 legal lines
  the-maximal-file.md      the wrapped form, block by block, with pointers
  the-formats.md           JSON or CSV, two sentences; CSV goes to Part II
  first-batch.md           preview, dry run, approve one, approve all
  after-you-send.md        batch show --all, job list, mail threads

03-keeping-it-running/
  the-daily-round.md       the 60-second ritual, and what normal looks like
  when-something-looks-wrong.md  one failure walked end to end
  stuck.md                 pause/resume at three levels, retry decisions
  taking-it-back.md        cancel vs delete vs force
  problems-list.md         the four places problems hide

04-mailboxes/
  many-mailboxes.md        fixed vs auto routing, the spread
  tune-a-mailbox.md        allowance, window, jitter, in-flight, --for
  move-and-pin.md          reassign, pin, unpin, in-flight refusal
  mailbox-states.md        pause, disable, archive, delete, unarchive
  broken-mailbox.md        needs_reauth, transports, keyring

05-follow-ups/
  the-thinking.md          suppression, no_reply, stop_on
  declare.md               shared vs payload, two real files, dry-run
  lifecycle.md             states, remove vs retire, version conflicts
  threading.md             the chain diagram

06-personalise/
  the-maximal-file-in-practice.md  variables, preview, test send
  csv-and-spreadsheets.md  one short page, de-weighted on purpose
  templates.md             short; the TOML contract lives in Part II
```

## Wiring and reuse

- Every mechanic term lives once in `glossary.md` (Part III) and is linked
  everywhere else. A term may not appear in a page unless the glossary has it.
- Every Part II pointer is written even when the target is a stub; Part II is
  then written to fill those named slots.
- `scripts/cli_tree.py` renders each page's command truth; Part II pages open
  with that render, and the future lint compares tree against book.

## Writing order

1. `02/one-email.md` as the template page. Get its voice approved, then every
   later page copies the motion.
2. `01/gmail.md` and `01/connect-a-mailbox.md`, the credential pain the user
   actually hits.
3. `03/the-daily-round.md` and `03/problems-list.md`.
4. `02/the-minimal-file.md`, `02/the-maximal-file.md`, then the rest of 02.
5. 04, 05, 06, then 01 remainder.
6. `glossary.md` grows continuously; it is never written in one sitting.

## Acceptance, per page

- Reads aloud like someone explaining to a friend.
- A reader who follows it at a terminal succeeds without opening Part II.
- Zero unexplained mechanic words; zero more than 3 flags; zero error-code
  tables.
- Frontmatter present; every pointer names a real or declared stub page.
- Under 120 source lines; longer means split.

# downcroc

downcroc is a local email orchestration daemon. It sends mail at volume from your own
accounts, watches what comes back, and attributes replies to the batch that caused them.

It is not a mail client. You draft elsewhere and hand downcroc a file. downcroc validates
it, schedules it, sends it, tracks it, and reports who answered.

The whole system is one background daemon that owns all state, and one or more clients
that attach to it and render what it says. Today the client is the command line. The TUI
described in `08-tui.md` and a later browser UI use the same API.

## Status of these documents

The daemon is the source of truth. These documents describe the system as it is understood
today, and they are expected to change as the build teaches us things. Where a document and the
code disagree, the code is right and the document is updated in the same change. Nothing here is
a contract to implement against.

Work items live in `.scratch/downcroc/issues/`, one file per ticket, numbered in dependency order.

## Architecture in one line

```
CLI / TUI / web client  ->  loopback HTTP + event stream  ->  daemon  ->  IMAP + SMTP  ->  providers
                                                          |
                                          SQLite (state, mail) + content store (bodies) + vault (credentials)
```

## Glossary

| Noun | Meaning |
|---|---|
| **Account** | one connected mailbox: Gmail, Outlook, or generic IMAP |
| **Attempt** | one OAuth connect flow in progress, alive independently of any client |
| **Batch** | the set of jobs created from one submitted file |
| **Job** | one email to one recipient. Retries alone, fails alone |
| **Message** | an actual email, sent or received |
| **Thread** | a conversation built from `Message-ID`, `In-Reply-To`, `References` |
| **Watcher** | a live IMAP IDLE connection ingesting new mail for one account |
| **Reply** | a received message whose thread was started by one of your jobs |
| **Event** | a recorded fact, sequenced and streamed to clients |
| **Vault** | the encrypted file holding credentials and nothing else |
| **Content store** | files on disk holding batches, templates, and attachments |

## Doc map

| File | Purpose |
|---|---|
| `01-architecture.md` | process model, thread split, on-disk layout, daemon lifecycle, module layout |
| `02-api-contract.md` | the HTTP contract, event stream, schemas, error model |
| `03-data-model.md` | SQLite schema, stored statistics, job state machine, content store, migrations, retention, durability |
| `04-security.md` | threat model, vault format, unlock lifecycle, the token invariant |
| `05-providers.md` | provider interface, Gmail, Outlook, generic IMAP, OAuth and XOAUTH2 |
| `06-send-pipeline.md` | inputs, validation, dry run, dispatch, quota, jitter, retries, suppression, follow-ups |
| `07-inbound.md` | watchers, IDLE, storage, DSN classification, threading, reply counting |
| `08-tui.md` | Textual client, screens, approval flow, config editing, design law |
| `09-backup-restore.md` | bundle format, versioning, forward migration, restore |
| `10-build-order.md` | phases and gates, live testing, code conventions, acceptance run |
| `11-decision-log.md` | every decision, its answer, and its rationale |
| `12-module-map.md` | module tree three levels deep, the seams, library homes, where new things go |

Reading order for a new contributor: `README` -> `01` -> `12` -> `03` -> `06` -> `07` -> `10`.

## What downcroc does

- Sends one email per recipient, from an account it has authenticated, at a rate and in a
  window you configure.
- Watches inboxes live and stores what arrives.
- Rebuilds threads and counts, per batch, how many people answered.
- Suppresses people who already replied, so follow-ups do not pester them.
- Survives restarts, reboots, sleeps, and network loss without losing or duplicating work.

## Non-goals

| Out of scope | Why |
|---|---|
| Composing mail in downcroc | You draft elsewhere. The TUI imports files |
| Scheduled send at a specific time | The queue drains a daily bucket. No delivery-time promise |
| Opt-out and unsubscribe handling | Personal outreach, not bulk marketing |
| Spam folder integration | INBOX only. Accepted accuracy cost |
| LLM features | No model dependency, no third-party data egress |
| Remote access | Loopback only, until it becomes a deliberate feature |
| Multi-user | One person, one machine |
| Mail server | downcroc reads and sends. It does not host |

## Known constraint

An unpublished Google OAuth client has refresh tokens that expire after seven days. downcroc
treats this as a first-class state, not a bug: the account moves to `needs_reauth`, jobs on
that account pause instead of failing, and the TUI shows a reconnect action. Publishing the
client is a later, separate piece of work.

## Fresh install

One daemon, no accounts, no vault, empty queue, no watchers. Every state in the system has a
defined empty form, and the first run must render that state rather than a stack trace.

---
title: account
commands: [account]
flags: [account.add --address, account.list --archived, account.attempt --client, account.connect --client, account.policy.set --daily-allowance, account.delete --dry-run, account.policy.set --for, account.delete --force-history, account.delete --force-jobs, account.add --imap-host, account.add --imap-port, account.add --imap-tls, account.policy.set --jitter-max, account.policy.set --jitter-min, account.transport.add --kind, account.add --label, account.transport.add --max-concurrency, account.transport.set --max-concurrency, account.policy.set --max-in-flight, account.transport.add --oauth-client, account.add --oauth-client-id, account.add --oauth-tenant, account.policy.set --on, account.transport.set --on, account.watch --on, account.add --password-file, account.connect --password-file, account.connect --password-stdin, account.transport.add --priority, account.transport.set --priority, account.add --provider, account.transport.add --rate-per-min, account.transport.set --rate-per-min, account.pause --reason, account.resume --reason, account.delete --reassign-to, account.attempt --redirect-url, account.connect --redirect-url, account.verify --refresh, account.add --smtp-host, account.add --smtp-port, account.add --smtp-tls, account.inbound --source, account.connect --transport, account.attempt --wait, account.policy.set --window-end, account.policy.set --window-start]
concepts: [needs-reauth, allowance, sending_window, jitter, max_in_flight]
screens: []
---

# account

`account` manages mail [[account]]s: the mailboxes downcroc sends from and, when enabled, watches for replies and bounces. With it you can add and connect mailboxes, inspect their state, verify and sync them, choose how inbound mail is read, control the watcher, pause or resume sending, archive or remove accounts, and configure their send [[transport]]s and per-account send policy.

## Usage

```text
downcroc account <action> [options]
```

Actions: `list`, `show`, `add`, `delete`, `deletion`, `archive`, `unarchive`, `providers`, `attempt`, `connect`, `verify`, `sync`, `inbound`, `pause`, `resume`, `watch`, `transport`, `policy`.

Many actions operate on a specific account and take an `account_id`. When an account id is required but omitted in interactive mode, downcroc can prompt you to choose one. Use `--json` for machine-readable output where supported.

## Listing and inspecting

### list

Lists accounts.

```text
downcroc account list [--archived]
```

- By default, `list` shows active (non-archived) accounts.
- `--archived` lists archived accounts instead.
- The listing shows configured accounts and their status (and other summary details). With `--json`, it prints the list as machine-readable JSON.

Use `list` to see what mailboxes exist, which are active, and (with `--archived`) which have been archived.

### show

Shows details for one account.

```text
downcroc account show [account_id]
```

- Displays the account’s details and current state/configuration (for example its status, provider and address, and related settings).
- With `--json`, prints the account as machine-readable JSON.

### providers

Lists providers and their readiness. This is an alias of `downcroc provider list`.

```text
downcroc account providers
```

It is a convenience so you can see available providers without leaving the account context.

### deletion

Previews what deleting an account would remove, without deleting anything.

```text
downcroc account deletion [account_id]
```

- Reports the impact associated with deleting the account: for example counts of jobs or history that would be affected. It is a dry look at the consequences of removal.
- Use this before `delete` to understand what will be removed and what you may need to reassign or force. With `--json`, prints the preview as machine-readable JSON.

## Adding and connecting

### add

Creates a new account in a pending state.

```text
downcroc account add [options]
```

- `--provider PROVIDER` selects the provider id. If omitted in interactive mode, you are asked to choose or enter it.
- `--address ADDRESS` sets the mailbox address. If omitted in interactive mode, you are asked for it.
- `--label LABEL` sets a display name for the account.
- **Connection overrides** (if you need to override the provider’s defaults): `--imap-host`, `--imap-port`, `--imap-tls {ssl|starttls|none}`, `--smtp-host`, `--smtp-port`, `--smtp-tls {starttls|ssl|none}`.
- **OAuth-related options** (where applicable): `--oauth-client-id`, `--oauth-tenant`, and `--password-file PATH` for an OAuth secret file.

`add` creates the account as pending so it can be connected next. After adding, connect it to provide or authorize credentials (see `connect` / `attempt`).

### attempt

Starts an OAuth connect attempt for an account.

```text
downcroc account attempt [account_id] [--wait] [--client ID] [--timeout SECONDS] [--redirect-url URL]
```

- Initiates the OAuth authorization flow for the account.
- `--client ID` selects a specific imported OAuth client to use (see `downcroc provider credentials`).
- `--wait` waits for the account to become connected. `--timeout TIMEOUT` controls how long to wait when `--wait` is set (default 180 seconds).
- `--redirect-url URL` is for headless flows: you supply the full loopback callback URL to deliver so the OAuth redirect can be completed without a local browser flow.

Use `attempt` when you need to drive or wait on the OAuth flow explicitly. `connect` also handles connecting accounts, including OAuth flows, and is the more general path.

### connect

Connects an account by providing or completing its credentials/sign-in.

```text
downcroc account connect [account_id] [options]
```

- **App-password authentication:** provide the app password via `--password-stdin` or `--password-file PATH`, or enter it interactively when prompted.
- **OAuth authentication:** you can select the imported OAuth client with `--client ID`. In headless scenarios, `--redirect-url URL` delivers the full loopback callback URL. After a successful OAuth connect, `--transport {smtp|gmail_api}` can select the binding/transport to create (where supported by the provider).
- On success the account becomes connected and its credential is stored for use (subject to the [[vault]] being unlocked).

If an account later loses access and becomes [[needs-reauth]], run `connect` again to re-authorize it.

### verify

Verifies that an account can sign in.

```text
downcroc account verify [account_id] [--refresh]
```

- Checks the account’s login/credential validity — that downcroc can authenticate as this mailbox.
- `--refresh` forces a re-check of the login now rather than relying on a previous result.

Use `verify` to confirm a mailbox can authenticate, especially after changing credentials, after re-authorizing, or when diagnosing access problems. (This is the transport/login verification for an account; to probe a specific send transport binding, use `account transport test`.)

## Receiving and watching

### sync

Requests an inbox sync for an account.

```text
downcroc account sync [account_id]
```

- Triggers a sync of the account’s inbox so recent messages can be picked up. The account must be connected for the sync to proceed.

### inbound

Chooses the inbound source used to read from a mailbox.

```text
downcroc account inbound [account_id] --source {auto|imap|gmail_api}
```

- `--source` is required.
- `auto` keeps IMAP and also sweeps with the Gmail API where applicable.
- `imap` uses IMAP for inbound mail.
- `gmail_api` uses the Gmail API for inbound. This is only available for mailboxes/providers that support Gmail API reads (for example an OAuth Gmail provider with the API configured). If the account/provider does not support it, the choice is rejected.

Changing the inbound source updates how the account is read for inbound messages (replies, bounces, and other inbound activity).

### watch

Enables or disables the watcher for an account.

```text
downcroc account watch [account_id] [--on|--off]
```

- `--on` starts/enables the watcher; `--off` stops/disables it.
- The watcher observes the mailbox (for example to detect replies and bounces) when enabled. Archiving an account stops its watcher.

## Pausing and resuming

Pausing an account stops sending from that mailbox without removing it. This is different from archiving (which removes it from active use), and different from pausing at the service, batch, or job level.

### pause

Pauses sending for one or more accounts.

```text
downcroc account pause <account_id> [account_id ...] [--reason REASON]
```

- Takes one or more account ids and pauses sending from those accounts.
- `--reason REASON` records why sending is paused.
- A paused account remains known and connected but does not send while paused.

### resume

Resumes sending for one or more accounts.

```text
downcroc account resume <account_id> [account_id ...] [--reason REASON]
```

- Takes one or more account ids and resumes sending from them.
- `--reason REASON` can record why sending is resumed.

## Archiving and removing

### archive

Archives an account and stops its watcher.

```text
downcroc account archive [account_id] [--yes]
```

- Moves the account out of the active set and stops its watcher so it is no longer used for new sending or watching. It asks for confirmation unless `--yes` is given.
- Archived accounts are not listed by default; list them with `downcroc account list --archived`. They can be restored with `unarchive`.

### unarchive

Restores an archived account.

```text
downcroc account unarchive [account_id] [--yes]
```

- Restores the account from the archived state. It asks for confirmation unless `--yes` is given.
- What happens on restore depends on credential availability: if credentials are present, the account can be made active for watching again; if credentials are missing, it may be marked as needing re-authentication ([[needs-reauth]]) so you can reconnect it.

### delete

Deletes an account.

```text
downcroc account delete [account_id] [options]
```

Deleting an account removes it. Because an account may own jobs or have history, deletion can have real impact. The command and its companion preview help you handle that safely:

- `--dry-run` shows what would be deleted without making changes.
- `--reassign-to ID` moves queued jobs to another account instead of deleting them with this account.
- `--force-jobs` allows deletion to proceed when unsent jobs would be removed.
- `--force-history` allows deletion of sent history as well.
- `--yes` skips the confirmation prompt.

Use `downcroc account deletion <id>` first to preview the impact. Reassign or account for work as needed before deleting an account that still owns jobs.

## Transports

```text
downcroc account transport <action> ...
```

Transports (bindings) define how an account sends mail — for example over SMTP or through the Gmail API. An account can have more than one transport. These commands list, add, change, remove, and test transports for an account.

### transport list

Lists send transports for an account.

```text
downcroc account transport list [account_id]
```

- Shows the transports/bindings configured for the account. With `--json`, prints them as machine-readable JSON.

### transport add

Adds a send transport to an account.

```text
downcroc account transport add [account_id] [options]
```

- `--kind {smtp|gmail_api}` selects how the mailbox sends (asked when omitted in interactive mode).
- `--priority PRIORITY` sets the transport priority. Higher priority transports are tried first.
- `--max-concurrency MAX_CONCURRENCY` sets parallel sends over the Gmail API (for API transports).
- `--rate-per-min RATE_PER_MIN` caps API calls per minute (for API transports).
- `--oauth-client ID` specifies the OAuth client used for the API transport.

### transport set

Changes an existing send transport.

```text
downcroc account transport set [account_id] [binding_id] [options]
```

- Identifies the transport by account and binding id.
- `--priority PRIORITY` updates priority.
- `--max-concurrency MAX_CONCURRENCY` updates parallel API send concurrency.
- `--rate-per-min RATE_PER_MIN` updates the per-minute API call cap.
- `--on` / `--off` enables or disables the transport without removing it.

### transport remove

Removes a send transport.

```text
downcroc account transport remove [account_id] [binding_id] [--yes]
```

- Removes the specified transport binding. Asks for confirmation unless `--yes` is given.

### transport test

Probes a send transport now.

```text
downcroc account transport test [account_id] [binding_id]
```

- Tests whether the specified transport can be used. This is useful for diagnosing send-route problems. It is distinct from `account verify`, which checks that the account itself can sign in.

## Policy

```text
downcroc account policy <action> ...
```

Manages the send policy for a specific account. An account can have a permanent policy override and, separately, a temporary override (with an expiry). The effective per-account policy is resolved from global settings together with these account overrides; limits from a batch may only tighten (slow) the effective behavior.

### policy show

Shows the effective policy for an account.

```text
downcroc account policy show [account_id]
```

- Displays the resolved values and the source of each value. It also shows the permanent account override and any active temporary override (including its expiry time) when present, so you can see exactly what is in effect and why.
- With `--json`, prints the policy view as machine-readable JSON.

### policy set

Sets an account policy override.

```text
downcroc account policy set [account_id] [policy fields] [--on|--off] [--for DURATION]
```

**Policy fields** (same meanings as the global send policy):

- `--daily-allowance N` — messages per mailbox per local day ([[allowance]]).
- `--window-start HOUR` and `--window-end HOUR` — local send window hours, inclusive start 0–23 and exclusive end 1–24, which must differ ([[sending_window]]).
- `--jitter-min SECONDS` and `--jitter-max SECONDS` — gap between sends in seconds ([[jitter]]).
- `--max-in-flight N` — concurrent sends per mailbox ([[max_in_flight]]).
- `--on` / `--off` — enable or disable sending for this account.

**Temporary vs permanent**

- With `--for DURATION` (for example `2h`, `7d`), the override is temporary and expires after the duration. While active it appears as a temporary override with an expiry in the effective policy.
- Without `--for`, the provided fields are applied as a permanent account override (merged with any existing permanent override for that account).

If you call `set` without providing any fields to change, the command fails with a usage error indicating that a field must be passed. After setting, the resulting effective policy is shown.

### policy clear

Removes the account policy override.

```text
downcroc account policy clear [account_id]
```

- Clears the account’s permanent policy override and any temporary account override, so the account falls back to underlying/global values. Shows the resulting effective policy.

### policy clear-temporary

Removes only the temporary account override.

```text
downcroc account policy clear-temporary [account_id]
```

- Clears the active temporary override while leaving the permanent account override in place. Shows the resulting effective policy.

Use this when you want a time-limited change to end now but keep the account’s standing (permanent) override.

## Examples

- `downcroc account list` — list active accounts and their status.
- `downcroc account list --archived` — list archived accounts.
- `downcroc account add --provider gmail --address you@example.com` — create a pending Gmail account.
- `downcroc account connect acct_123` — connect an account (prompting or using provided credentials/flow).
- `downcroc account attempt acct_123 --wait` — start an OAuth attempt and wait for it to complete.
- `downcroc account verify acct_123 --refresh` — re-check the account login now.
- `downcroc account sync acct_123` — request an inbox sync.
- `downcroc account inbound acct_123 --source gmail_api` — read inbound via the Gmail API (when supported).
- `downcroc account watch acct_123 --off` — disable the watcher for an account.
- `downcroc account pause acct_123 acct_456 --reason "rate limit"` — pause sending for two accounts.
- `downcroc account resume acct_123` — resume sending for an account.
- `downcroc account deletion acct_123` — preview what deleting an account would remove.
- `downcroc account transport list acct_123` — list send transports for an account.
- `downcroc account transport test acct_123 trn_123` — probe a send transport.
- `downcroc account policy set acct_123 --daily-allowance 50 --for 2h` — set a temporary daily allowance for an account.
- `downcroc account policy clear-temporary acct_123` — remove only the temporary policy override.

## See also

- [../06-provider/provider.md](../06-provider/provider.md) — provider declarations and OAuth client credentials
- [../11-sending/sending.md](../11-sending/sending.md) — global send policy and overrides
- [../04-vault/vault.md](../04-vault/vault.md) — unlock the vault so credentials can be used
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose account, auth, and transport issues
- [../part-i/01-starting/connect-a-mailbox.md](../part-i/01-starting/connect-a-mailbox.md) — connecting a mailbox
- [../part-i/01-starting/gmail.md](../part-i/01-starting/gmail.md) — Gmail setup and sign-in
- [../part-i/04-mailboxes/many-mailboxes.md](../part-i/04-mailboxes/many-mailboxes.md) — using more than one mailbox
- [../part-i/04-mailboxes/tune-a-mailbox.md](../part-i/04-mailboxes/tune-a-mailbox.md) — tuning a mailbox
- [../part-i/04-mailboxes/move-and-pin.md](../part-i/04-mailboxes/move-and-pin.md) — moving and pinning work between mailboxes
- [../part-i/04-mailboxes/mailbox-states.md](../part-i/04-mailboxes/mailbox-states.md) — pausing, archiving, and account states
- [../part-i/04-mailboxes/broken-mailbox.md](../part-i/04-mailboxes/broken-mailbox.md) — fixing a mailbox that needs attention

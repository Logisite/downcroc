---
title: init
commands: [init]
flags: [--service, --no-service, --account-provider, --account-address]
concepts: [vault]
screens: []
---

# init

`init` runs first-time setup for downcroc. It prepares the local environment, helps you start or install the daemon, sets up the [[vault]], and can guide you through adding and connecting a first account. You typically run it once on a new machine; after that, day-to-day use is `service start`/`vault unlock` and the normal commands.

## Usage

```text
downcroc init [--service | --no-service]
              [--account-provider PROVIDER] [--account-address ADDRESS]
```

## Options

`--service`
: Install the daemon as a login service during setup, so it can be managed as a service.

`--no-service`
: Leave the daemon running detached for this session instead of installing it as a login service.

`--service` and `--no-service` cannot be used together. If you pass neither in interactive mode, `init` asks you how you want the daemon to run.

`--account-provider ACCOUNT_PROVIDER`
: The provider id for the first mailbox to add (for example `gmail`, `gmail-app-password`, `microsoft`, or `generic`).

`--account-address ACCOUNT_ADDRESS`
: The email address for the first mailbox to add.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## What init does

`init` walks through setup in stages. In interactive mode it explains what it is about to do and asks before making changes; in non-interactive/JSON mode it reports state and requires the information it needs to be supplied explicitly.

### 1. Paths and confirmation

`init` resolves and shows the config, data, and state paths that downcroc will use on this machine. In interactive mode it asks for confirmation before continuing, so you can see where things will live.

### 2. Daemon and service

`init` checks whether the daemon is already running. If it is not, it decides how to start it:

- **`--service`**: installs the login service (if not already installed) and starts it.
- **`--no-service`**: starts the daemon now, detached for this session, without installing a login service.
- **Interactive, no flag**: lets you choose — run it now, install it as a login service (recommended), or skip starting it for now.

If the daemon is already running, `init` notes that and continues. In non-interactive JSON mode it reports the current daemon status as part of its summary.

### 3. Vault

`init` checks the [[vault]] state and makes sure you have a usable vault:

- **Already unlocked:** continues.
- **Vault exists but is locked:** reports that it is locked. In interactive mode it can offer to unlock it now.
- **No vault exists:** guides you through creating one. The vault password protects every mail credential and **cannot be recovered** if lost. If the system credential store is available, interactive mode can offer to store the password there so you do not have to retype it on future unlocks; if the store is unavailable, you type the password instead.

In non-interactive mode, creating a missing vault requires the password to be provided (for example via a password file/stdin as supported by the vault flow). If the password cannot be obtained non-interactively, `init` fails with a hint to create the vault (see `downcroc vault init`).

### 4. First account (optional)

If accounts are already configured, `init` reports that and skips adding one. Otherwise it can help you add and connect a first mailbox:

- **Choosing the mailbox:** `--account-provider` and `--account-address` specify the mailbox to add. If a provider is not given in interactive mode, you can choose a provider or skip adding an account for now.
- **Gmail:** you choose how to sign in (OAuth client or app password). If an OAuth client is needed and not ready, `init` can guide you through importing it (see `downcroc provider credentials set`).
- **Generic/custom IMAP:** in interactive mode, `init` collects the server and security settings and writes them to the provider configuration so the account can be added.
- **Creating and connecting:** `init` creates the account and, when possible, continues into connecting it. If connecting fails, the password/credential is not saved and `init` tells you how to resume with `downcroc account connect <id>`.

If the first account ends up connected, interactive mode can offer to send a test message to that address.

## Output

On completion, `init` reports a summary (for example the daemon state and whether an account was added/connected) and suggests `downcroc status` as a next step to confirm everything is healthy. With `--json` it prints a machine-readable summary including paths, daemon state, and the account id when one was created.

## Examples

- `downcroc init` — run interactive first-time setup.
- `downcroc init --service` — run setup and install the daemon as a login service.
- `downcroc init --no-service` — run setup and start the daemon detached without installing a login service.
- `downcroc init --account-provider gmail --account-address you@example.com` — run setup and add a first Gmail account.

## See also

- [../part-i/01-starting/first-run.md](../part-i/01-starting/first-run.md) — the first-run walkthrough
- [../part-i/01-starting/turn-it-on.md](../part-i/01-starting/turn-it-on.md) — starting the daemon
- [../01-service/service.md](../01-service/service.md) — manage the daemon as a service
- [../04-vault/vault.md](../04-vault/vault.md) — create, inspect, and unlock the credential vault
- [../06-provider/provider.md](../06-provider/provider.md) — provider declarations and OAuth client credentials
- [../07-account/account.md](../07-account/account.md) — manage and connect mail accounts
- [../02-status/status.md](../02-status/status.md) — check overall status after setup

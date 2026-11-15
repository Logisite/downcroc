---
title: vault
commands: [vault]
flags: [vault.lock --forget, vault.init --keyring, vault.keyring --keyring, vault.unlock --keyring, vault.init --password-file, vault.keyring --password-file, vault.unlock --password-file, vault.init --password-stdin, vault.keyring --password-stdin, vault.unlock --password-stdin]
concepts: [vault]
screens: []
---

# vault

`vault` manages the credential [[vault]]: the protected store that holds your mail credentials. With it you create the vault, check whether it is locked or unlocked, unlock it so credentials can be used, lock it again, and control whether the master password is kept in the system credential store.

The vault is the boundary around secrets. When it is locked, downcroc cannot use the credentials inside it. When you unlock it, those credentials become available to the daemon until the vault is locked again. A clean daemon shutdown locks the vault automatically, so every time you start the daemon (for example with `downcroc service start` or `downcroc serve`) you should expect to unlock the vault before anything that needs credentials can work.

## Usage

```text
downcroc vault <action> [options]
```

Actions: `status`, `init`, `unlock`, `lock`, `keyring`.

If you run `downcroc vault` without an action in interactive mode, downcroc offers a menu so you can pick the action. In non-interactive mode (for example with `--no-input` or when not attached to a terminal) an action is required.

## Actions

### status

Shows the current state of the vault. This action only reads state; it never changes it.

**What it tells you**

- Whether the vault is `locked` or `unlocked`, and the path to the vault file.
- When the vault is unlocked, the time it was unlocked (when that information is available).
- When the vault is locked, it also reports how many unlock attempts remain and any retry delay before another unlock attempt is allowed. These details matter if an unlock was tried with the wrong password: downcroc limits attempts and can require you to wait before trying again.

**Output**

- Default: a human-readable summary of the state and path, including lock/attempt details when the vault is locked.
- `--json`: a machine-readable view of the vault state. The JSON form focuses on the vault state itself (it omits the accounts listing that the underlying status may include).

Use `status` whenever you want to confirm whether the vault is ready for credential use, or to understand why an unlock is not being accepted yet (remaining attempts, retry delay).

### init

Creates a new vault. You run this once, when no vault exists yet.

**When you can run it**

- `init` only works if a vault does not already exist at the vault path. If a vault already exists, `init` fails with `vault_exists` and tells you to run `downcroc vault unlock` instead. It will not overwrite or replace an existing vault.

**The master password**

- You must choose a master password. This password protects every mail credential stored in the vault. It **cannot be recovered** if you lose it, so keep it somewhere safe.
- How to provide it: you can pass it non-interactively with `--password-stdin` (read from standard input) or `--password-file PATH` (read from a file at `PATH`; the file should be protected, for example permissions mode 0600, because it contains the vault password). If neither flag is provided, `init` prompts you to enter the password and asks you to enter it again to confirm it matches.

**Storing the password in the system credential store**

- When a password is supplied successfully and keyring use is allowed (see [Password and keyring options](#password-and-keyring-options)), downcroc may store the password in the system credential store so future unlocks can use it without you retyping it.
- In interactive flows such as first-run setup, you may be offered the choice to store it. If the system credential store is unavailable, you will need to type the password when unlocking.

**On success**

- `init` reports the vault state. In interactive mode (when not running with `--quiet`) it suggests a next step, such as adding an account.

### unlock

Unlocks an existing vault so the stored credentials can be used by the daemon.

**If it is already unlocked**

- `unlock` does not change anything and reports that the vault is already unlocked. In JSON output this is reflected as `changed: false`.

**How the password is obtained**

The master password is required unless it can be read from the system credential store. downcroc looks for it in this order:

1. If you provided `--password-stdin` or `--password-file PATH`, the password is read from there.
2. Otherwise, if keyring use is not disabled (`--no-keyring` was not set) and a stored password exists in the system credential store, the stored password is used.
3. If you explicitly asked to use the keyring (`--keyring`) but no stored password is available in a way the operation can use, the command fails because the store cannot provide the password (see the keyring section for what that means).
4. Otherwise, if the session is interactive, you are prompted to enter the password.
5. If no password can be obtained and input is not interactive, the command cannot prompt and fails rather than hanging.

**What happens on success**

- The vault becomes unlocked and the command reports its state (`changed: true` in JSON). If the password came from the system credential store, the output notes that it was unlocked using the system credential store.
- When a password is supplied successfully and keyring use is allowed, downcroc may store it in the system credential store for future unlocks (so you may not need to type it next time).

**What happens on failure**

- If the unlock attempt fails after using a stored password, that stored password is removed. This prevents a bad or stale stored entry from repeatedly blocking you; you can provide the correct password and, if desired, store it again.

Unlock is needed after starting the daemon and any time the vault has been locked (including after a clean shutdown, which locks it).

### lock

Locks the vault.

**Behavior**

- Locks the vault and reports its locked state. Once locked, credentials in the vault cannot be used until you unlock again.
- A clean daemon shutdown locks the vault automatically; you can also lock it explicitly at any time with this command.

**Forgetting the stored password (`--forget`)**

- With `--forget`, `lock` also deletes the stored master password from the system credential store. This removes only the copy saved in the credential store; it does **not** change or reset the master password itself, and it does not affect the vault contents.
- After forgetting, future unlocks will require you to provide the password again (by prompt, `--password-file`, or `--password-stdin`). If you want downcroc to remember it in the system credential store again later, you can re-enable storage with `downcroc vault keyring enable`.
- The command reports that the stored password was deleted and reminds you the master password is unchanged, suggesting `downcroc vault keyring enable` if you want to store it again.

**Output**

- Default: reports the vault state and, if `--forget` was used, notes that the stored password was deleted.
- `--json`: prints the state and, when applicable, whether the stored password was forgotten/removed.

### keyring

Shows or controls use of the system credential store for the vault master password.

```text
downcroc vault keyring <status|enable|disable> [options]
```

The credential store (keyring) lets downcroc save the vault master password in your system's credential store so you do not have to type it on every unlock. Whether it is available depends on your environment.

#### keyring status

Reports the state of the system credential store integration. This is read-only.

- Shows whether the credential store is available, its name, and, if it is unavailable, the reason it is unavailable.
- With `--json`, prints `available`, `name`, and `reason`.

Use this to find out if downcroc can remember the password on this machine, or why it cannot.

#### keyring enable

Stores the master password in the system credential store.

- Requires the credential store to be available. If it is not available, the command fails with `keyring_unavailable` and a hint to run without `--keyring` and type the password instead.
- You must provide the master password so it can be stored: pass it with `--password-stdin` or `--password-file PATH`, or enter it at the interactive prompt.
- On success it reports that the keyring is on and names the store.
- With `--json`, prints that the keyring is enabled and the store name.

After enabling, unlocks can use the stored password (subject to normal unlock behavior) so you do not have to retype it each time.

#### keyring disable

Removes the stored master password from the system credential store.

- Reports that the keyring is off and that unlocking will prompt for the master password again.
- With `--json`, prints that the keyring is off and whether a stored entry was removed.

Disabling does not change the master password or the vault; it only stops downcroc from keeping a saved copy in the system credential store.

## Password and keyring options

These options control how the master password is provided and whether the system credential store is read or written. They apply to `init`, `unlock`, and `keyring enable` (and `keyring` accepts them for password input).

`--password-stdin`
: Read the master password from standard input. Useful for non-interactive or scripted input where you do not want to place the password in a command-line argument.

`--password-file PATH`
: Read the master password from a file at `PATH`. The file should be protected (for example permissions mode 0600) because it contains the vault password.

`--keyring`
: Use the system credential store. A stored password can be read from it when needed, and a supplied password may be saved to it when allowed. If you explicitly request `--keyring` but the store cannot satisfy the operation (for example it is unavailable, or no stored password exists when one is required), the command fails with a keyring-unavailable error and a hint to type the password instead.

`--no-keyring`
: Do not read from and do not write to the system credential store for this operation, even if a stored password exists.

If neither a password flag is provided nor a usable stored password is available, and the session is not interactive, the command cannot prompt and will fail.

## Other options

`--forget`
: Used with `lock`. Deletes the stored master password from the system credential store. The master password itself is unchanged.

Common flags (available on vault commands): `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc vault status` — show whether the vault is locked or unlocked, its path, and any lock/attempt details.
- `downcroc vault init` — create a new vault, prompting for a master password and confirmation.
- `downcroc vault init --password-file /run/secrets/downcroc` — create the vault reading the master password from a protected file.
- `downcroc vault unlock` — unlock the vault (prompting for the password, or using the stored password if available).
- `downcroc vault unlock --password-file /run/secrets/downcroc` — unlock using a password read from a file.
- `downcroc vault unlock --no-keyring` — unlock without reading or writing the system credential store.
- `downcroc vault lock` — lock the vault.
- `downcroc vault lock --forget` — lock the vault and remove the stored master password from the system credential store.
- `downcroc vault keyring status` — report whether the credential store is available.
- `downcroc vault keyring enable` — store the master password in the credential store for future unlocks.
- `downcroc vault keyring disable` — remove the stored master password from the credential store.

## See also

- [../part-i/01-starting/first-run.md](../part-i/01-starting/first-run.md) — the first-run walkthrough, including creating the vault
- [../03-init/init.md](../03-init/init.md) — first-time setup, including vault creation and unlocking
- [../02-status/status.md](../02-status/status.md) — vault state shown in the overall system status
- [../01-service/service.md](../01-service/service.md) — starting the daemon (unlock the vault after start)
- [../01-service/serve.md](../01-service/serve.md) — running the daemon in the foreground
- [../19-logs/events/vault.md](../19-logs/events/vault.md) — log events for vault actions and errors
- [../part-iii/34-safety.md](../part-iii/34-safety.md) — how credentials and data are protected

# 04 - Security

## What this system is defending

One person's mail accounts, on one machine, used to send a lot of individual email. The assets,
in order:

1. **Credentials.** OAuth refresh tokens and app passwords. A stolen refresh token lets someone
   read and send from your mailbox indefinitely, invisibly, from anywhere.
2. **Mail content.** Conversations, attachments, correspondents.
3. **Sending capability.** The ability to make your address send mail at volume.

The threat model is small and specific. It is not a web service. There is no untrusted network
peer, no multi-tenancy, no privilege boundary between users.

## In scope

| Threat | Response |
|---|---|
| Laptop stolen or disk imaged | vault.enc is the only credential store, Argon2id + AES-256-GCM |
| Backup file copied | the bundle contains the vault, which is useless without the password |
| Credentials leaking through the API | no endpoint, event, log line, or error ever contains a token |
| Accidental log capture | tokens are redacted at the logging boundary, not at each call site |
| A local process reading the live API | accepted, documented, not defended (below) |
| Restart resetting rate limits | quota buckets are durable |

## Explicitly out of scope

| Threat | Why not defended |
|---|---|
| Malicious process running as the same user | it can read the unlocked daemon's memory and the SQLite file; no local design survives this |
| Other local users | see below |
| Root or physical access | out of reach |
| Provider-side compromise | not ours |
| Mail content confidentiality at rest | deliberate: bodies are plaintext in SQLite |

## The honest statement about local access

The API is loopback-bound and requires a per-run bearer token. Any local process that can read
`daemon.token` as the same user can:

- read stored mail
- enqueue a batch within your configured allowance
- read the config
- trigger a connect attempt

While the daemon is unlocked, it can also **send** using your accounts, because the daemon holds
the key in memory and the token only identifies a caller that can already read the state
directory.

The token is not a defence against a process running as you. It removes the accidental exposure
where any local process, including one running as another user, could drive the API. The
alternative considered was a unix socket with peer credentials, which is not portable to
Windows and does not help once the attacker is already the same user.

The mitigation that actually matters is unchanged: **the daemon starts locked, unlock is an
explicit human act, and stopping the daemon discards the key.** Host and Origin validation stop
a browser page or a DNS-rebound request from reaching the API, and `/docs`, `/redoc`, and
`/openapi.json` are disabled so the surface is not advertised. There is no browser login,
cookie, pairing flow, or GUI session.

If remote access is ever built, it ships with a pairing flow and the loopback assumption is
re-opened in `11-decision-log.md`.

## Vault format

`vault.enc` sits beside the database and holds credentials and nothing else. Mail bodies are
not encrypted, because encrypting the thing you query on every screen buys little against an
attacker who already has the disk and the password prompt.

### Structure

| Part | Content |
|---|---|
| Magic and version | `DNCROC1`, format version, KDF parameters, salt, nonce |
| Digest | SHA-256 over the header and ciphertext, checked before decryption |
| Ciphertext | AES-256-GCM over a CBOR map of `credential_key -> secret` |
| Tag | authenticated by GCM, covers header fields as additional data |

The header is authenticated as AAD, so editing KDF parameters, algorithm ids, or the format
version makes decryption fail rather than silently weakening the file. The digest is unkeyed and
is not a security boundary: it exists so an accidental byte flip is reported as corruption
instead of a wrong password. A tampered file that recomputes the digest still fails GCM.

### Key derivation

Argon2id with parameters recorded in the header. At creation the daemon starts at the configured
floor (64 MiB memory, 3 iterations, 1 lane) and doubles memory, up to a configured ceiling
(256 MiB), until a derivation reaches the configured target (250 ms). The chosen parameters are
read from the header on unlock, so a vault created on a slower machine still opens.

The derived key is used directly for AES-256-GCM. No key wrapping, no second layer.

### Writes

Atomic replace only: write to `vault.enc.tmp` in the same directory, `fsync` the file,
`os.replace`, `fsync` the directory. A failed write unlinks the temporary file and leaves the
old vault intact. A crash leaves either the old vault or the new one, never a truncated one.
The digest, then the magic and version checks, report damage as corruption rather than as a
wrong password.

### What lives inside

| Key | Value |
|---|---|
| `acct_<id>:refresh_token` | OAuth refresh token |
| `acct_<id>:access_token` | cached access token, with its expiry, so a restart does not re-refresh |
| `acct_<id>:app_password` | generic IMAP password, when that is the auth kind |

The OAuth client id lives in provider configuration. An optional client secret lives beside it in
`providers.toml` or a `providers.d` declaration, mode `0600`, never in the vault and never in an
API response. It is a desktop public client, so PKCE is the proof; the secret is sent only when a
provider requires one.

Access tokens are cached inside the vault so restarting the daemon does not burn a refresh, and
so an expiry can be honoured precisely.

## The OAuth connect boundary

The connect flow is the one place where a credential arrives from outside the daemon, so its
rules are explicit.

| Rule | Detail |
|---|---|
| Bind address | the callback listener binds `127.0.0.1` only, on an ephemeral port |
| State | 32 random bytes, stored on the attempt, compared with `hmac.compare_digest` |
| PKCE | S256, 64 random bytes, verifier in memory for the attempt only, never persisted |
| Attempt lifetime | `[connect].oauth_attempt_ttl_s`, default 600 seconds; a late callback is rejected |
| One pending attempt | a second start for the same account returns `attempt_pending` |
| Restart | pending attempts become `expired` with `daemon_restart`; no flow resumes across a restart |
| Token transport | authorization and token URLs must be `https`, except loopback for a local test server |
| Callback response | `no-store`, `no-referrer`, `nosniff`, and no provider response body |
| Error surface | provider error codes are matched against a small pattern; anything else becomes `oauth_failed` |
| Token write | access and refresh tokens are written in one vault transaction |
| Access token cache | cleared only by a lock; refresh happens under a per-account lock |

The authorization code is short-lived and single-use at the provider. The daemon does not log it,
store it, or include it in an event. The refresh token is the durable credential and lives in the
vault.

## Unlock lifecycle

```
start locked  ->  POST /api/vault/unlock  ->  key in memory  ->  POST /api/vault/lock
                       |                                             |
                       | derive, decrypt, verify                     | zeroise, emit vault.locked
                       v                                             v
                  emit vault.unlocked                          jobs in flight finish or are abandoned
```

Rules:

- The password is received once, held only long enough to derive, then dropped. It is never
  written, logged, or returned.
- The derived key lives in the process only. No key file. The optional system credential store
  holds the master password, never the key (see below).
- Failed unlock attempts are counted and rate limited in memory: five free attempts, then an
  exponentially increasing delay from one second, capped at five minutes. The free count, base
  delay, and ceiling are in `[vault]`. This is not a defence against an attacker with the file
  (they can brute force offline) but it does stop a runaway script from spinning the CPU.
- A successful unlock resets the failure count. A corrupt file is refused without counting as a
  password attempt, stays locked, and logs the offset and expected value.
- Unlocking with a vault file that does not exist creates it. This is the first-run path.
- Unlocking an already unlocked vault returns `vault_already_unlocked`; locking a locked vault is
  a no-op.
- Unlocking with a wrong password fails cleanly with `vault_bad_password`, with no hint about
  which part failed.
- Locking while sends are in flight: the sender finishes the current message if it can within
  its lease, then stops. Jobs left in `sending` follow the normal crash path in `03`.
- Stopping the daemon locks. There is no separate step and no way to stop it unlocked.

## The system credential store (optional)

By default the master password is typed at every unlock. A user may instead let downcroc keep it
in the operating system credential store, so the only password they remember is the one they use
to log in to the computer. The decision is `Q81` in `11-decision-log.md` and the CLI behaviour is
the vault password sources subsection of section 6.1 in `13-interactive-cli.md`.

| Rule | Detail |
|---|---|
| Default | off. `vault init` offers it, `--no-keyring` refuses it, and `--no-input` never enables it |
| Store | Secret Service over D-Bus on Linux, Windows Credential Manager on Windows. Nothing else is accepted |
| Item | service `downcroc`, account `<absolute vault path>`, so two installations do not collide |
| Value | the master password exactly as entered. Never the derived key, never a mailbox password |
| Reader | the CLI only. The daemon still starts locked and receives the password through `/api/vault/unlock` |
| Write | after the vault is created and verified. A store failure leaves the vault usable and prints a warning |
| Removal | `vault keyring disable`, or `vault lock --forget`, deletes the item. The vault password does not change |
| Backend absent | `keyring unavailable`, one line, then the normal prompt. Headless Linux has no Secret Service, so this is the common server case |
| Backend refused | a file or plaintext backend is refused with `keyring_backend_unsupported` and treated as absent. `keyrings.alt` is not a dependency |
| Frozen binary | ticket 06 must include the backend imports, or the binary reports the store as unavailable instead of crashing |

The threat model changes while this is on. Any process running as the same user in the same
logged-in session can ask the store for the item and unlock the vault without knowing anything.
The vault still protects a stolen disk, a stolen backup, and a copied data directory, because
none of those include the OS session. It does not protect against code already running as the
user, and neither did the typed password: that password passed through the CLI's memory, and the
derived key sits in the daemon while it runs. The prompt states the trade in one line, the
`vault` help topic states it in full, and the choice is per installation.

Windows note: the Credential Manager item belongs to the user's logon. A scheduled task that runs
whether or not the user is logged on cannot read it, so the vault stays locked there. The logon
task used by `service install` runs in the interactive session and can.

Linux note: Secret Service needs a session bus and an unlocked login keyring. A server reached
over SSH usually has neither, so the store reports unavailable and the prompt remains the path.

## Daemon bearer token

The daemon writes a per-run bearer token to `daemon.token` in the state directory at startup.
It is 32 random bytes encoded as URL-safe text, mode `0600` on Unix and an owner-only ACL on
Windows, and never appears in a log, event, API response, error message, or backup bundle. The
token is removed on clean stop and rotated on every start. The CLI reads it from the state
directory and sends it as a bearer token. Release 1 applies the token to every route except
`GET /api/health` and the OAuth callback, which is protected by its state nonce.

Requests must also present a trusted loopback `Host` and, when present, a loopback `Origin`;
anything else is rejected with `403`. `POST /api/service/stop` uses the same token and sets the
server shutdown flag, so shutdown runs the normal application lifespan. `downcroc auth status`
reports whether the token is present and accepted without printing it.

## The token invariant

**A credential never leaves the daemon.**

Concretely, all of the following are forbidden and are checked at the boundary:

| Surface | Rule |
|---|---|
| HTTP responses | no field may contain a token, a password, or a client secret |
| Events | payloads carry account ids and status, never credential material |
| Logs | a redaction filter runs on every record; values matching token shapes become `***` |
| Error messages | provider errors are mapped to codes; raw provider responses are truncated and scrubbed |
| TUI | renders `credential_present: true`, never the credential |
| Backups | bundles include `vault.enc`, which is encrypted anyway |
| Crash dumps | a deliberate risk: a dump of the process may contain the key. Not defended |

Authentication and leak tests check the boundary: a missing, malformed, or wrong token is
rejected, an untrusted Host or Origin is rejected, a restart invalidates the previous token,
and logs, API errors, and backup bundles are searched for the daemon token. Inside the daemon
the provider-secret invariant is still structural: secrets live in a single object owned by
`core/vault_service.py`, and nothing outside the provider and mail layers can obtain one.
`VaultService.get_secret` is the only accessor; it requires an unlocked vault, raises
`vault_locked` otherwise, and no HTTP route imports it.

## Filesystem permissions

| Path | Mode |
|---|---|
| `~/.config/downcroc/` | `0700` |
| `config.toml`, `providers.toml` | `0600` |
| `providers.d/*.toml` | `0600` |
| `vault.enc` | `0600` |
| `~/.local/share/downcroc/` | `0700` |
| `downcroc.db` | `0600` |
| `logs/` | `0700` |
| `~/.local/state/downcroc/` | `0700` |
| `service.json` | `0600` |
| `daemon.token` | `0600` |
| `daemon.lock` | `0600` |

The daemon checks these at startup and corrects a looser mode with a warning in the log rather
than refusing to start. Refusing to start would lock a user out of their own tool over a `chmod`.
Windows uses `%APPDATA%\\downcroc` for config and `%LOCALAPPDATA%\\downcroc` for data and state.
POSIX modes do not apply there; credential files such as `daemon.token` and `vault.enc` get an
owner-only ACL with inheritance removed.

## Failure modes

| Situation | Behaviour |
|---|---|
| Wrong password | `vault_bad_password`, no detail, attempts rate limited |
| Credential store item missing | `keyring_empty`, then the normal password prompt |
| Credential store unreachable | `keyring_unavailable`, then the prompt; the vault is unaffected |
| Credential store holds a stale password | the item is deleted, the prompt appears with a one-line note, and a successful typed unlock offers to store the new password |
| Vault truncated or corrupt | `vault_corrupt` with instructions to restore from backup; the daemon stays up, locked |
| Disk full during vault write | old vault intact, operation fails, error surfaced |
| Provider revokes the refresh token | account to `needs_reauth`, jobs on that account pause, no failures recorded |
| Provider returns a scope error | same, with the missing scope named in the account view |
| OAuth callback state mismatch | 400 page, attempt stays pending, and the operator can cancel or let it expire |
| OAuth URL is not https | provider declaration refused at startup unless the host is loopback |
| Provider file is group readable | chmod to `0600`, `provider.permissions` warning, startup continues |
| Clock jumps backwards | backoff timers clamp; quota buckets are keyed by local date so a jump cannot double-spend a day |
| Two daemons started | the lock file wins, the second exits with a clear message |

## Non-goals worth stating

- No encryption of mail bodies. If the disk is the threat, the vault protects the keys and the
  mail is readable. This is disclosed, not hidden.
- No audit trail of who read what. Single-user local tool.
- No secret scanning of logs beyond the credential patterns, because the logs contain mail
  subjects and agent addresses by design.

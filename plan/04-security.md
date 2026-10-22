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

The API is loopback-bound and unauthenticated. Any local process can:

- read stored mail
- enqueue a batch within your configured allowance
- read the config
- trigger a connect attempt

While the daemon is unlocked, it can also **send** using your accounts, because the daemon holds
the key in memory and the API has no way to tell a legitimate TUI from anything else.

This was a considered decision. The alternatives were a token the TUI must store (which is a
second credential with no stronger protection than the first) or a unix socket with peer
credentials (which defends against other users, on a machine where the other users are already
trusted or the box is already lost).

The mitigation that actually matters is the one already in place: **the daemon starts locked,
unlock is an explicit human act, and stopping the daemon discards the key.** On a machine where
you are the only interactive user, the practical exposure is that a compromised local process
can act as you while you are working. That process could already read your SSH keys.

If remote access is ever built, it ships with a token and a pairing flow, and the loopback
assumption is re-opened in `11-decision-log.md`.

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
| `acct_<id>:client_secret` | only when a provider needs a per-account secret |

Access tokens are cached inside the vault so restarting the daemon does not burn a refresh, and
so an expiry can be honoured precisely.

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
- The derived key lives in the process only. No key file, no keyring integration.
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

No test is required for this. It is enforced structurally instead: secrets live in a single
object owned by `core/vault_service.py`, and nothing outside the provider and mail layers can
obtain one. `VaultService.get_secret` is the only accessor; it requires an unlocked vault,
raises `vault_locked` otherwise, and no HTTP route imports it.

## Filesystem permissions

| Path | Mode |
|---|---|
| `~/.config/downcroc/` | `0700` |
| `config.toml`, `providers.toml` | `0600` |
| `vault.enc` | `0600` |
| `~/.local/share/downcroc/` | `0700` |
| `downcroc.db` | `0600` |
| `logs/` | `0700` |

The daemon checks these at startup and corrects a looser mode with a warning in the log rather
than refusing to start. Refusing to start would lock a user out of their own tool over a `chmod`.

## Failure modes

| Situation | Behaviour |
|---|---|
| Wrong password | `vault_bad_password`, no detail, attempts rate limited |
| Vault truncated or corrupt | `vault_corrupt` with instructions to restore from backup; the daemon stays up, locked |
| Disk full during vault write | old vault intact, operation fails, error surfaced |
| Provider revokes the refresh token | account to `needs_reauth`, jobs on that account pause, no failures recorded |
| Provider returns a scope error | same, with the missing scope named in the account view |
| Clock jumps backwards | backoff timers clamp; quota buckets are keyed by local date so a jump cannot double-spend a day |
| Two daemons started | the lock file wins, the second exits with a clear message |

## Non-goals worth stating

- No encryption of mail bodies. If the disk is the threat, the vault protects the keys and the
  mail is readable. This is disclosed, not hidden.
- No audit trail of who read what. Single-user local tool.
- No secret scanning of logs beyond the credential patterns, because the logs contain mail
  subjects and agent addresses by design.

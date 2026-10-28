# 03 - The vault locks and unlocks

**What to build:** a master password sets up the vault. Secrets are sealed with Argon2id and
AES-256-GCM behind a versioned authenticated header, written by atomic replace, readable only
while unlocked. Unlock and lock are endpoints. Wrong passwords are refused and rate limited from
config, and a corrupted file is reported rather than crashed on. A restart comes up locked.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] first unlock with no vault creates it with a fresh salt, at mode `0600`
- [ ] lock drops the key in memory; a secret read after lock fails with a stable code
- [ ] a wrong password is refused, counted, and throttled at the configured threshold
- [ ] flipping one byte in the file reports corruption and does not unlock
- [ ] writing a secret twice leaves no temporary file behind and never a half-written vault
- [ ] restart reports `locked` and the vault opens with the same password
- [ ] no secret value appears in a log line or an API response

**Logs:** the events this ticket introduces. No secret, password, key, or token appears in any of
them, at any level.

- `vault.created` path, kdf params
- `vault.unlocked` duration_ms
- `vault.unlock_failed` attempts_left
- `vault.locked` reason
- `vault.corrupt` offset, expected
- `vault.sealed` bytes, duration_ms

**Commit:** `feat(vault): add key derivation, sealed store, unlock lifecycle`

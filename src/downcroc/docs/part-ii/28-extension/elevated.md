---
title: Elevated extensions
commands: []
flags: []
concepts: []
screens: []
---

# Elevated extensions

Some extensions need to do more than reply to mail. They may need to call an
external API with a stored credential, change config, control the service, or
read and write vault secrets. Those are elevated capabilities. They are not
available to a standard extension, even if the manifest asks for them.

## The layers

Layer 0 is the daemon itself. Vault files, SQLite, service objects, and signal
handling live here. No extension ever gets direct access. Capabilities call
into Layer 0 on your behalf.

Layer 1 is a standard extension. It runs as a child process, speaks JSON, and
can use only standard capabilities.

Layer 2 is an elevated extension. It still runs as a child process by default
and still speaks JSON, but after approval it may call elevated capabilities.
Every call is still logged.

## Declaring an elevated extension

Set the tier in the manifest:

```toml
id = "crm-sync"
name = "CRM sync"
version = "1.0.0"
tier = "elevated"
events = ["reply.attributed"]
capabilities = [
  "message.get",
  "http.request",
  "cli.run",
  "notify",
  "kv.get",
  "kv.set",
  "log",
]
```

A standard manifest that requests an elevated capability is refused when the
daemon loads it. The error names the capability that needs the higher tier.

## Approving

Install and reload first:

```sh
downcroc extension add crm-sync.pyz
downcroc extension reload
```

Then approve:

```sh
downcroc extension approve crm-sync
```

The command prompts for the vault password. If the vault is locked, the same
password is used to unlock it and approve the extension. If the vault is
already unlocked, you are still prompted. Approval is per extension. There is
no global session that skips the prompt for the next one.

The daemon stores an approval record with the extension id, a digest of the
manifest, a digest of the capability set, the tier, and the approval time. It
does not store the password or a derived key. The log records only that
approval happened.

Check status with:

```sh
downcroc extension approval crm-sync --json
```

## When approval is revoked

Approval is tied to the exact manifest. It is revoked automatically when:

- the artifact checksum changes
- the capability list changes
- the tier changes
- the manifest is replaced with a different version

Reload after a change and approve again. This prevents a maintainer from
silently adding a dangerous capability to an already approved extension.

You can also revoke explicitly:

```sh
downcroc extension revoke crm-sync
```

Revocation stops the running process. It does not delete the manifest or the
artifact.

## Vault lock behavior

If the vault locks after approval, the approval remains. It is a trust decision
about code, not a session credential. Capability calls that need secrets fail
with `vault_locked` until you unlock again. Calls that do not need secrets,
such as `kv.get` or `log`, keep working.

Unlocking with `downcroc vault unlock` does not re-approve anything. It only
restores access to secrets for already approved extensions.

## http.request

This is the general escape hatch for custom network work.

```json
{
  "capability": "http.request",
  "params": {
    "credential": "account:acct_1",
    "method": "POST",
    "url": "https://api.example.com/messages",
    "headers": {"Content-Type": "application/json"},
    "body": {"text": "hello"}
  }
}
```

The credential reference is a label, not a secret. Supported forms are
`account:<id>`, `provider:<name>:<account>`, and `secret:<key>`. The daemon
resolves the reference, injects the Authorization header, performs the request,
and returns the status and sanitized response body. The extension never sees
the token.

By default the host must be granted explicitly:

```toml
allow = ["http.request:api.example.com"]
```

A request to any other host is denied before any network call. A wildcard
`http.request:*` allows any host and should be used only for code you trust.

The result looks like:

```json
{"ok": true, "value": {"status": 200, "body": {"id": "msg_9"}}}
```

## cli.run

This runs a real downcroc CLI command inside the daemon environment.

```json
{"capability": "cli.run", "params": {"argv": ["--version"]}}
```

`argv` must be a list of strings. `["status", "--json"]` works. A string is also
accepted and split with shell-style rules, but a list is clearer and preferred.
No shell is used.

The result contains `returncode`, `stdout`, and `stderr`:

```json
{"ok": true, "value": {"returncode": 0, "stdout": "downcroc 1.3.6\n", "stderr": ""}}
```

The daemon redacts the bearer token from both output fields before returning
them. Output is truncated to 8000 characters per stream. A command that times
out raises `ExtensionTimeout` and is logged.

## notify

This records a notification request in the daemon log. It does not open a
desktop window by itself.

```json
{"capability": "notify", "params": {"message": "CRM sync finished"}}
```

## Other elevated families

- `config.set` applies a validated config patch.
- `policy.set` and `policy.clear` change send policy for an account or globally.
- `quota.set`, `hold.set`, `hold.clear`, `dispatch.pause`, and `dispatch.resume`
  change runtime sending behavior.
- `vault.lock`, `vault.unlock`, `secret.put`, `secret.delete`, and `key.rotate`
  manage vault state. Secret values are never returned.
- `transport.*` and `provider.set_override` change transport configuration.
- `backup.*`, `export.json`, and `import.json` manage portability.
- `db.vacuum`, `db.integrity_check`, `stats.rebuild`, and `stats.prune` perform
  maintenance.
- `timer.*`, `command.register`, and `extension.approve` extend runtime
  behavior and are granted only by explicit config.

Some names in these families are registered but not yet backed by a full daemon
operation. They return a structured acknowledgement and are logged. Check the
release note for your version before relying on their side effects.

## Safety rules

Elevated does not mean unrestricted. The following are never exposed:

- raw credential read
- arbitrary shell execution
- arbitrary filesystem access
- direct SQLite access
- arbitrary Python import into the daemon process

An elevated extension is still an untrusted program with a narrow, audited
interface. Grant only what it needs.

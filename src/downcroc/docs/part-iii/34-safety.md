---
title: Safety
commands: [vault, service, backup, restore, status]
concepts: [vault, daemon, account, batch, job]
---

# Safety

downcroc is designed to keep control and secrets local to the machine running it.
This chapter describes the guarantees and boundaries the system enforces: how
credentials are protected, what the [[daemon]] exposes, and which actions are (and
are not) taken on your behalf.

For operational controls, see [service](../part-ii/01-service/service.md),
[vault](../part-ii/04-vault/vault.md), and [Configuration reference](38-config.md).

## The daemon and its local boundary

The daemon owns state and performs work (sending, watching, syncing). It listens
on a local loopback address only; it is not meant to be bound or exposed beyond
loopback.

The HTTP API is protected on that local boundary:

- Requests must present the expected Host and Origin for the local daemon; other
  hosts/origins are rejected.
- API requests require the per-run bearer token issued for the daemon, except for
  the health endpoint and the OAuth callback path which are public by design.
- Authentication and request rejections are logged as structured events without
  exposing secrets.

Other downcroc commands talk to the running daemon over this local API. If the
daemon is not running, work is not being processed.

## The vault and credentials

The [[vault]] holds secrets (such as account credentials). It has two states:
**locked** and **unlocked**. downcroc starts locked; you must unlock the vault
before credentials can be used. A clean stop locks the vault again.

Unlocking is protected against repeated bad passwords: after the allowed free
attempts, further attempts are throttled with an increasing delay. The vault
reports its state, path, and (when relevant) retry/attempt information without
revealing secret material.

Credentials are treated as sensitive everywhere:

- They must never appear in logs, events, API responses, or error messages.
- Operational output reports presence/status (for example whether an [[account]] has
  a usable credential, or needs reauth) rather than the secret itself.

Treat `daemon.token`, the vault, and the service/state files as local secrets of
the installation: they grant or protect access to the running daemon and stored
credentials.

## Data, state, and isolation

Configuration, data, state, and logs live under the application’s directories
(see `downcroc status` for resolved paths). Tests and live checks should be
isolated from real config/database/vault/logs so they do not touch a real
installation.

Inbound watcher/ingest work is separated from state mutation boundaries in the
system’s design; the daemon coordinates work so state changes are owned and
recorded consistently.

## Controls that hold work vs controls that remove it

Safety also means being explicit about effect:

- **Pausing** (service, account, batch, or job) holds dispatch. It prevents
  future sends while the hold is active; it does not cancel, delete, or rewrite
  jobs or batches, and it does not recall mail already in flight or already sent.
- **Cancelling** stops work from being sent (subject to what is already in
  flight) and records a terminal stopped state; it is different from a pause.
- **Deleting/reassigning/portability operations** follow their own rules and
  guards (for example conflicts when work is in flight or not in an allowed
  state). Use dry-run/preview options where provided and read the command
  contract before destructive actions.

When you need sending to stop immediately at the service level, pause or stop the
daemon; when you need to understand impact, inspect state (`status`, `batch
show`, `job show`) before acting.

## Backups and restore

Backup and restore commands exist to move or preserve installation data under the
tool’s control. Credentials and secrets must not be exposed in logs, events, API
responses, or backup bundles. Treat produced bundles and any restore markers/state
as sensitive operational artifacts and handle them with the same care as the data
directories they represent.

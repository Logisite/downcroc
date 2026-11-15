---
title: Account and authentication log events
commands: []
flags: []
concepts: [needs-reauth]
screens: []
---

# Account and authentication log events

Events for account lifecycle, login/authentication checks, and provider/OAuth authentication. Primary emitters: `src/downcroc/core/accounts/service.py`, `src/downcroc/core/accounts/login.py`, `src/downcroc/core/accounts/lifecycle.py`, `src/downcroc/core/accounts/preflight.py`, `src/downcroc/providers/token.py`, `src/downcroc/providers/registry.py`, `src/downcroc/core/holds.py` (account pause/resume).

## Account lifecycle and holds

- `account.created` (**info**) — an account was created.
  - `account`: account id.
  - `provider`: provider id (and related context as emitted).

- `account.paused` (**info**, log; also published) — sending was paused for an account.
  - `account`: account id.
  - `reason`: pause reason.
  - Published/impact fields may include `auto_jobs`, `pinned_jobs`, `lost_lanes`, `absorbed_by` (as computed).

- `account.resumed` (**info**, log; also published) — sending was resumed for an account.
  - `account`: account id.
  - `reason`: resume reason (as provided).
  - May include impact such as held jobs.

## Authentication and login

- `account.needs_reauth` (**warning**) — the account can no longer be used with its current credentials and needs re-authentication ([[needs-reauth]]).
  - Typically includes `account` and `reason` (as emitted).

- `account.auth_check_cancelled` (**info**) — an authentication/login check was cancelled.
  - `reason`: cancellation reason.

- `imap.login` (**info** on success, **warning** on failure) — outcome of an IMAP login attempt.
  - `account`: account id.
  - `outcome`: result classification (e.g. `ok` on success, or a failure classification on failure).
  - Additional connection/auth detail fields may be included as emitted for the attempt.

- `oauth.failed` (**warning**) — an OAuth/token operation failed.
  - Typically includes `code` and `account` (as emitted).

- Provider/permission related warnings or errors (e.g. `provider.permissions`) may be emitted when provider/client permissions or configuration affect operation; consult the specific record for its fields.

## Account connection and OAuth

- `account.connected` (**info**, log; also published) — an account was connected/authenticated successfully.
  - `account` (log) / account `id` (published) and provider/auth context as emitted.

- `oauth.started` (**info**) — an OAuth authorization flow was started.
  - Attempt/client/account/provider context as emitted.

- `oauth.callback` (**info**, when emitted) — an OAuth callback was received/processed.
  - Attempt/state context as emitted.

- `oauth.token` (**info**, when emitted) — an OAuth token was obtained/refreshed.
  - Account/client context as emitted (secrets are redacted).

- `oauth.expired` (**info/warning**) — an OAuth attempt/token flow expired.
  - Attempt/account context and reason as emitted.

- `oauth.cancelled` (**info**) — an OAuth flow was cancelled.
  - Attempt/account context as emitted.

- `oauth.failed` (**warning**) — an OAuth/token operation failed.
  - Typically includes `code` and `account` (and detail as emitted).

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../07-account/account.md](../../07-account/account.md) — manage accounts and policy
- [../../05-auth/auth.md](../../05-auth/auth.md) — authentication commands/flows
- [../../06-provider/provider.md](../../06-provider/provider.md) — providers and credentials
- [../../part-i/04-mailboxes/broken-mailbox.md](../../part-i/04-mailboxes/broken-mailbox.md) — fixing a mailbox that needs attention

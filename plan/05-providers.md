# 05 - Providers

## Principle

A provider is data plus four operations. Nothing in the queue, the client, or the API knows
which provider it is talking to. Adding one means adding a declaration, not editing a branch.

Built-in declarations ship with the package. Users can override them or add their own in
`~/.config/downcroc/providers.toml`. Code contains no hardcoded Gmail path.

## The interface

Four operations, each with a narrow signature.

| Operation | Input | Output |
|---|---|---|
| `send` | account, rendered message bytes, envelope | accepted, or a classified error |
| `fetch` | account, folder, uid range | raw messages plus UIDs |
| `idle` | account, folder, timeout | change signal, or timeout |
| `validate` | account | ok, or a reason code |

Everything a provider needs to know about network behaviour is declared, not derived:

| Declaration | Purpose |
|---|---|
| `smtp_host`, `smtp_port`, `smtp_tls` | where and how to submit |
| `imap_host`, `imap_port`, `imap_tls` | where and how to read |
| `auth_kind` | `oauth2`, `app_password`, or `none` |
| `smtp_auth_mechanism` | `XOAUTH2` or `PLAIN` |
| `oauth_authorize_url`, `oauth_token_url`, `oauth_scopes`, `oauth_redirect` | the connect flow |
| `sent_folder` | where to look for our own sent messages, for reconciliation |
| `supports_idle` | whether a live watcher is possible |
| `requires_user_agent` | a few servers reject empty UA |
| `notes` | shown in the TUI when the provider is selected |

## Declarations

Shipped defaults, abbreviated:

| Field | gmail | microsoft | generic |
|---|---|---|---|
| smtp | `smtp.gmail.com:587`, STARTTLS | `smtp.office365.com:587`, STARTTLS | configured |
| imap | `imap.gmail.com:993`, TLS | `outlook.office365.com:993`, TLS | configured |
| auth | oauth2 | oauth2 | app_password |
| SMTP mechanism | XOAUTH2 | XOAUTH2 | PLAIN |
| scopes | `https://mail.google.com/` | `SMTP.Send`, `IMAP.AccessAsUser.All`, `offline_access` | none |
| authorize | `accounts.google.com/o/oauth2/v2/auth` | `login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize` | none |
| token | `oauth2.googleapis.com/token` | `login.microsoftonline.com/{tenant}/oauth2/v2.0/token` | none |
| IDLE | yes | yes | declared |
| sent folder | `[Gmail]/Sent Mail` | `Sent Items` | declared |

The Gmail scope choice is deliberate. `https://mail.google.com/` is the single scope that
covers SMTP send and IMAP read in one grant. Using `gmail.send` plus `gmail.modify` works too and
is narrower, but it is still restricted, so the consent screen is the same. One scope is fewer
moving parts. Documented here so the choice is not mistaken for carelessness.

Microsoft needs a tenant. `common` works for personal and most work accounts; a work tenant with
sign-in restrictions needs its own id. This is a config field, not a code change.

## The OAuth connect flow

The daemon owns the flow. The client only starts it and polls.

```
POST /api/accounts/{id}/attempts
        |
        v
  daemon creates state token, opens loopback listener on an ephemeral port
        |
        v
  returns { attempt_id, authorization_url, expires_at }
        |
        v   user opens the URL in a browser, chooses an account, consents
  provider redirects to http://127.0.0.1:{port}/callback?code=...&state=...
        |
        v
  daemon verifies state, exchanges code for tokens, validates by opening IMAP
        |
        v
  writes tokens to the vault, sets account status connected, emits account.connected
```

Details that matter:

- **Loopback redirect, not a custom scheme or out-of-band.** Google dropped OOB; loopback with
  an ephemeral port is the only flow that works on a desktop with no hosted callback.
  The exact redirect URI is registered per client and must be `http://127.0.0.1` with any port,
  so the port can vary.
- **`state` is a nonce stored on the attempt**, so a stray callback cannot attach an account.
- **Attempts expire** after 10 minutes. An expired attempt is persisted as `expired`, not
  deleted, so the TUI can show what happened.
- **Attempts survive client disconnects**, because they belong to the daemon. Closing the TUI
  mid-consent does not lose the flow; reopening shows the same attempt.
- **`access_type=offline` and `prompt=consent`** for Google, otherwise no refresh token on
  re-authorisation. Microsoft needs `offline_access` in the scope list.
- **Client secrets** are optional. A desktop client is a public client, so PKCE is used and the
  secret is only stored when a provider genuinely requires one.
- **The callback listener closes on completion, failure, or expiry**, and its port is released.
  No listener outlives its attempt.

## XOAUTH2

Both Gmail and Microsoft accept SASL XOAUTH2 for SMTP. The string is built at send time from a
freshly guaranteed access token:

```
user=<address>\x01auth=Bearer <access_token>\x01\x01
```

This is handed to `aiosmtplib` through its native `auth_xoauth2` support, with
`oauth_token_generator` supplying the token so a mid-session expiry triggers one refresh rather
than a failed send.

For IMAP, `imap-tools` builds the same string internally via its `xoauth2` helper. No separate
XOAUTH2 package is needed anywhere in the dependency set, and adding one would be a second
implementation of the same eleven bytes.

Consequence worth writing down: the access token is materialised into a string just before the
connection, which is the narrowest window available. It is not kept as a module-level variable,
and it is not cached in plaintext outside the vault.

## Token lifecycle

```
vault (refresh)  ->  access token in memory, with expiry  ->  connection
                              ^                                  |
                              |____ refresh on 401 / expiry ____|
```

| Rule | Detail |
|---|---|
| Refresh proactively | if the cached token expires within 120 seconds, refresh before connecting |
| Refresh reactively | a 401 or an XOAUTH2 failure triggers one refresh and one retry, never a loop |
| Persist refreshed tokens | new access token and its expiry go back into the vault immediately |
| Never refresh concurrently for one account | one lock per account, so two jobs starting together do not race the token endpoint |
| A failed refresh is not a send failure | the account moves to `needs_reauth`, and its queued jobs stay queued |

## `needs_reauth` as a first-class state

An unpublished Google client's refresh tokens expire after **seven days**. This is not a bug to
work around; it is the environment. Any design that treats auth expiry as an exception will be
wrong most of the time.

So:

- The account record carries `status = needs_reauth` with the reason and the timestamp.
- Jobs bound to that account **pause in `queued`**. They do not attempt, do not consume an
  attempt number, and do not fail.
- The dispatcher skips the account entirely while it is in this state.
- The TUI shows a persistent, non-modal banner and a reconnect action on the account row.
- Reconnecting is just a new attempt. On success, the account returns to `connected` and the
  queued jobs drain on the next tick.
- Other accounts are unaffected. One expired Google grant never stops the daemon.
- If every account is in `needs_reauth`, the queue holds and the dashboard says why. It does
  not silently idle.

The same state covers a revoked grant, a password change, and a scope the user removed. The
cause is recorded in `last_error`, and the message never contains token material.

## Generic IMAP

For any server that does not do our OAuth flows: host, port, TLS mode, username, app password.
The credential goes into the vault exactly like an OAuth token, under the same key scheme.

| Consideration | Handling |
|---|---|
| App passwords are often required | documented per-provider in the TUI note field |
| Some servers reject the default User-Agent | `requires_user_agent` declaration |
| Some servers have no IDLE | `supports_idle = false` falls back to polling every N minutes |
| Sent folder names vary | declared, with a short probe list as fallback (`Sent`, `Sent Items`, `Sent Mail`, `[Gmail]/Sent Mail`) |
| Certificates | verified always. No self-signed escape hatch in the first build |
| Failed auth | `needs_reauth` with the server's reason code, never the password |

The fallback probe only runs once, and the resolved folder is recorded on the account so it is
not rediscovered on every reconciliation.

## Capability differences the clients must respect

| Capability | Effect on the UI |
|---|---|
| `supports_idle = false` | watcher shows "polling every 5 min", not "live" |
| No Sent folder found | reconciliation of `sent_unconfirmed` is unavailable; the state is surfaced, not hidden |
| Quota unknown | the daily allowance is purely the user's own number, with no provider cross-check |
| Attachment size cap | declared per provider, validated before the job is created rather than at send time |

Nothing here is silently degraded. If a capability is missing, the account view says so, because
a user who thinks a watcher is live when it is polling will misread their own reply counts.

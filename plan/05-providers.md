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
| `oauth_authorize_url`, `oauth_token_url`, `oauth_scopes` | the connect flow |
| `oauth_client_id`, `oauth_client_secret`, `oauth_tenant` | the client registration |
| `oauth_extra_params` | provider specific authorize parameters, such as `access_type` |
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

## Where declarations live

The registry reads three places, in this order:

1. The built-in declarations inside the package, `providers/declarations/*.toml`.
2. `~/.config/downcroc/providers.toml`, whose `[providers.<id>]` tables are partial overrides of a
   built-in or complete declarations for a new provider.
3. `~/.config/downcroc/providers.d/*.toml`, sorted by filename, each a complete declaration with a
   top-level `id`. Later files override earlier ones.

The order is the precedence order. A user can set only `oauth_client_id` under
`[providers.gmail]`, or add a completely new provider under `[providers.fastmail]` with every
required field. No code changes, no rebuild. An unknown field is an error, not a silent ignore:
the daemon refuses to start, logs `provider.registry_failed` with the file and field, and names
the same field in the startup error.

Provider files are credential material even when they contain only a client id. A file readable
by group or other is chmodded to `0600` and a `provider.permissions` warning is logged. The
vault is still the only place refresh tokens and app passwords live.

One transport exception is deliberate: `imap_tls = "none"` is accepted only for `127.0.0.1`,
`::1`, and `localhost`. It exists for a local test server, never for a real mailbox. `ssl` and
`starttls` always verify certificates.

## The OAuth connect flow

The daemon owns the flow. The client only starts it and polls.

```
POST /api/accounts/{id}/attempts
        |
        v
  daemon creates state token and PKCE verifier, opens loopback listener on an ephemeral port
        |
        v
  returns { id, account_id, kind, state, authorization_url, expires_at, created_at, error }
        |
        v   user opens the URL in a browser, chooses an account, consents
  provider redirects to http://127.0.0.1:{port}/callback?code=...&state=...
        |
        v
  daemon verifies state, exchanges code for tokens, validates by opening IMAP
        |
        v
  writes refresh and access tokens to the vault in one transaction, sets account connected,
  emits account.connected
```

Details that matter:

- **Loopback redirect, not a custom scheme or out-of-band.** Google dropped OOB; loopback with
  an ephemeral port is the only flow that works on a desktop with no hosted callback.
  The exact redirect URI is computed per attempt and is not a declaration field. Google accepts
  `http://127.0.0.1` with any port, so the port can vary.
- **`state` is a nonce stored on the attempt**, compared with `hmac.compare_digest`. It is
  returned only inside the authorization URL, never as its own API field. A stray callback cannot
  attach an account.
- **PKCE is S256.** The verifier is random, lives in memory for the life of the attempt, and is
  never persisted or returned. The challenge is in the authorization URL.
- **Attempts expire** after `[connect].oauth_attempt_ttl_s`, default 600 seconds. An expired
  attempt is persisted as `expired`, not deleted, so the TUI can show what happened. A callback
  that arrives after expiry is rejected and the listener closes.
- **Attempts survive client disconnects**, because they belong to the daemon. Closing the TUI
  mid-consent does not lose the flow; reopening shows the same attempt.
- **One pending attempt per account.** A second start returns `attempt_pending` with a hint naming
  the attempt to cancel. `POST /api/attempts/{id}/cancel` marks it `cancelled` and releases the
  listener. A crash leaves the row `pending`; startup marks it `expired` with `daemon_restart`, so
  a restart never resumes an authorization the browser may have abandoned. A clean shutdown marks
  pending attempts `expired` with `daemon_stopped`.
- **`access_type=offline` and `prompt=consent`** are declared in the Gmail
  `oauth_extra_params`, otherwise a re-authorisation can omit the refresh token. Microsoft needs
  `offline_access` in the scope list.
- **Client ids are provider configuration**, under `[providers.gmail]` in `providers.toml` or in
  a declaration. Client secrets are optional and are sent only when the declaration sets one. A
  desktop client is a public client, so PKCE is the proof, not the secret.
- **The callback listener closes on completion, failure, cancellation, or expiry**, and its port
  is released. No listener outlives its attempt.
- **A password provider never starts an attempt.** It connects through
  `POST /api/accounts/{id}/connect` with `{"password": "..."}`; the password goes from the request
  body to IMAP to the vault, and never to a log, event, or response.

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
| Cache access tokens | the access token and its expiry are stored in the vault, so a restart does not refresh |
| Refresh proactively | if the cached token expires within `[connect].token_refresh_margin_s` (default 120), refresh before connecting |
| Refresh reactively | an IMAP auth failure triggers one refresh and one retry, never a loop |
| Force a refresh | `POST /api/accounts/{id}/verify?refresh=true` refreshes before connecting, which detects a revoked grant at once |
| Persist refreshed tokens | the new access token and expiry go back into the vault immediately; a rotated refresh token replaces the old one, and a missing one keeps the old |
| Never refresh concurrently for one account | one lock per account, so two jobs starting together do not race the token endpoint |
| `invalid_grant` | the account moves to `needs_reauth` with that reason |
| Token endpoint unreachable | `oauth_unavailable` (502), the status is left alone |
| Any other token error | `oauth_failed` (502), the status is left alone |
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
| Certificates | verified always. No self-signed escape hatch in the first build; plaintext `none` is loopback only |
| Failed first connect | 401 `imap_auth_failed`, the account stays `pending`, and no credential is stored |
| Failed verify | the account moves to `needs_reauth` with `last_error = imap_auth_failed` |

The fallback probe only runs once, and the resolved folder is recorded on the account so it is
not rediscovered on every reconciliation.

The connect call is `POST /api/accounts/{id}/connect` with `{"password": "..."}`. The daemon
tries IMAP before writing anything, then stores the password under `<account>:app_password` and
marks the account `connected`. The password is not echoed by any response, event, or log line.

## Capability differences the clients must respect

| Capability | Effect on the UI |
|---|---|
| `supports_idle = false` | watcher shows "polling every 5 min", not "live" |
| No Sent folder found | reconciliation of `sent_unconfirmed` is unavailable; the state is surfaced, not hidden |
| Quota unknown | the daily allowance is purely the user's own number, with no provider cross-check |
| Attachment size cap | declared per provider, validated before the job is created rather than at send time |

Nothing here is silently degraded. If a capability is missing, the account view says so, because
a user who thinks a watcher is live when it is polling will misread their own reply counts.

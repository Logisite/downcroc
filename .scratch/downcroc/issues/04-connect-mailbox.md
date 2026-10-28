# 04 - One real mailbox connects

**What to build:** providers are declared in TOML files loaded by a registry, not hardcoded.
A Gmail account connects through an OAuth flow with a loopback callback, a state nonce and PKCE;
the refresh token goes into the vault; the access token builds the XOAUTH2 string; an IMAP login
proves the credential works and the account becomes `connected`. A revoked grant turns into
`needs_reauth`, not a failure. A generic IMAP account with an app password connects through the
same path with no OAuth.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] a new declaration file is picked up without touching code
- [ ] Gmail connect completes in a browser, the callback is verified against the state nonce
- [ ] IMAP login with XOAUTH2 succeeds and the account is `connected`
- [ ] restart and unlock leave the account connected without a new browser flow
- [ ] revoking the grant and running any account operation yields `needs_reauth`
- [ ] an app password account connects and logs in
- [ ] no token reaches a log, an event payload, or an API response

**Logs:** the events this ticket introduces. Token values are never logged, only their lifetime
and scope count.

- `provider.registry` declarations, count
- `oauth.started` provider, account
- `oauth.callback` state_ok, elapsed_ms
- `oauth.token` expires_in, scopes
- `oauth.failed` code
- `token.refreshed` account, duration_ms, expires_in
- `account.needs_reauth` reason
- `imap.login` host, duration_ms, outcome

**Commit:** `feat(connect): add provider registry, oauth flow, xoauth2, imap verify`

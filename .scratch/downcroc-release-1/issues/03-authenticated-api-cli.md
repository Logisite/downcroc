# 03 - Authenticated daemon API and CLI

**What to build:** the daemon generates a per-run bearer token at startup, stores it under the state directory with restrictive permissions, and requires it on every API route except public health and the OAuth callback. Extend the control token from ticket 01 to full API authentication. The CLI reads the token automatically so existing commands keep working. Validate Host and Origin, disable public FastAPI documentation endpoints, rotate the token on every start, and add `downcroc auth status`. Ensure the token never reaches logs, events, API responses, backups, or error messages. Update the architecture, security, decision-log, and module records, plus the repository guidance that currently says the API is unauthenticated.

**Blocked by:** 01 - Portable daemon lifecycle on Linux and Windows.

**Status:** ready-for-agent

- [ ] Health remains reachable without a token
- [ ] Every other API route rejects a missing, malformed, or wrong token with 401
- [ ] The CLI attaches the current token automatically and all existing CLI commands work unchanged
- [ ] The OAuth callback works without a bearer token but still requires a valid state nonce
- [ ] A restarted daemon issues a new token and rejects the previous token
- [ ] The token file is readable only by the owning user
- [ ] Host and Origin validation rejects requests with untrusted values
- [ ] Public `/docs`, `/redoc`, and `/openapi.json` endpoints are disabled, while `downcroc openapi` still exports a valid document
- [ ] `downcroc auth status` reports whether the token exists and is accepted without printing the secret
- [ ] Tokens and authorization headers never appear in logs, events, API errors, or backup bundles
- [ ] Authentication and leak tests are green on Linux and Windows
- [ ] The architecture, security, and repository guidance describe the authenticated API and the absence of browser login or GUI sessions

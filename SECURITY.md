# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.3.x | yes |
| 1.2.x and older | no |

Security fixes land on the latest patch release. If you run an older release, upgrade before
reporting a vulnerability that may already be fixed.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability
reporting on the repository:

https://github.com/Logisite/downcroc/security/advisories/new

Include:

- the affected version and platform
- a short description of the impact
- reproduction steps or a proof of concept
- whether the issue requires a local user, the daemon API, a provider, or a crafted input
- any suggested fix

Do not include real credentials, tokens, mailbox contents, or personal addresses. Replace them
with synthetic values.

## What to expect

- Acknowledgement within 3 working days.
- A triage decision within 10 working days.
- A coordinated disclosure date after a fix is available.
- Credit in the release note unless you ask to stay anonymous.

## Scope

In scope:

- the local daemon, HTTP API, CLI, vault, backup and restore, and installer scripts
- credential handling and log redaction
- authentication and loopback boundary checks
- crafted campaign, CSV, template, backup, or follow-up input
- dependency vulnerabilities that affect a shipped artifact

Out of scope:

- a user who can already read the daemon's config, data, state, or memory
- provider account suspensions or deliverability decisions
- social engineering
- macOS, which is outside the release 1 support scope

## Safe harbour

Good-faith research that follows this policy is welcome. Do not access data that is not yours, do
not disrupt a running service, and do not test against accounts or mailboxes you do not own.

---
title: Connect a mailbox
description: Add a mailbox, choose OAuth or an app password, and verify it.
tags: [accounts, oauth, imap, smtp]
audience: user
status: stable
since: 1.3.1
order: 10
related:
  - concepts/smtp-seats.md
terminal:
  summary: Add an account, connect it, then run doctor.
---

# Connect a mailbox

## Add the account

```sh
downcroc account add --provider gmail --address you@example.com
```

The command returns an account id.

## Connect it

```sh
downcroc account connect ACCOUNT_ID
```

Gmail uses OAuth. A generic IMAP provider uses an app password.

!!! note "Credential check"
    After vault unlock, downcroc checks every stored credential in the background. The interactive
    startup shows a compact credential strip.

## Verify it

```sh
downcroc doctor
downcroc account show ACCOUNT_ID
```

A connected account has `credential_present: true`, a connected status, and a healthy transport
binding.

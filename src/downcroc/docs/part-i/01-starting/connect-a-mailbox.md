---
title: Connect a mailbox
commands: [account.add, account.connect, account.verify]
concepts: [vault, job]
screens: []
---

# Connect a mailbox

downcroc can only send from an address you have given it permission to use.
Connecting a mailbox is how you grant that permission: you tell it which
address to send from, and you prove, once, that you can sign in to it. After
that, the daemon can send on your behalf until the mailbox or its password
changes.

## Adding the mailbox

From the main menu choose **account**, then **add**. The editor asks for the
pieces downcroc needs to know about this mailbox. The most important ones are
the provider and the address: the provider tells downcroc what kind of
mailbox it is, and the address is the one your messages will come from.

```text
↑↓ move · enter edit · x clear · b back · r run · q quit
```

Fill in the address and pick the provider that matches it. For many mailboxes
the provider is enough for downcroc to know where to connect; some setups ask
for more detail. When the lines read right, press `r`. downcroc creates the
account and gives it a name inside the app, but it is not ready to send yet.
It knows *which* mailbox you mean; it does not yet have a way in.

## Connecting it

Still in the **account** menu, choose **connect** and pick the account you
just added. This is the step where you hand over the credential: a password,
or another sign-in method the provider uses. What you enter here goes into the
[[vault]], not into a message and not into a log.

When the connection succeeds, the account is ready. downcroc can now sign in
and send from that address, and any [[job]] you point at it has somewhere to
leave from.

## Making sure it works

If you want to be certain before you rely on it, choose **verify** for the
same account. Verify asks the mailbox to confirm that the sign-in still works
right now. It is a small check, and it is worth doing the first time, because
a mailbox that looks added but cannot sign in will only show its trouble when
you try to send.

If verify reports that the mailbox cannot connect, nothing you queued is lost.
The fix is usually to connect it again with the right credential, and then
try once more.

> What "ready" means
>
> An account is ready when downcroc can sign in to it. Added but not
> connected means downcroc knows the address; connected means it can speak
> for it. A [[job]] sent from a mailbox that is not ready will wait rather
> than pretend to leave.

The same thing, typed: `downcroc account add`, then
`downcroc account connect <account>`, then `downcroc account verify <account>`.

⤷ every field on the account screens, including provider and server details:
  [../part-ii/07-account/account.md](../part-ii/07-account/account.md)
⤷ connecting a Gmail mailbox and keeping it connected:
  [gmail.md](gmail.md)

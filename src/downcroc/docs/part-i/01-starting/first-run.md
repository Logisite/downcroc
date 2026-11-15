---
title: First run
commands: [init, vault.init, vault.unlock, vault.lock, vault.status, auth.status]
concepts: [vault, daemon]
screens: []
---

# First run

The first time you run downcroc, there are two things to set up before it can
do any real work. It needs a place to keep secrets, and it needs you to open
that place once so it knows you are there. After that, starting a day is much
quieter.

## Getting set up

From the main menu, choose **init**. The editor that opens asks a few small
questions about how you want this machine set up, including whether the daemon
should be installed as a service so it can run in the background on its own.
You move through it the same way as any other editor: arrows to move, enter
to change a line, `r` to run when it looks right.

```text
↑↓ move · enter edit · x clear · b back · r run · q quit
```

Running init creates the directories and files downcroc needs. It does not
connect a mailbox yet and it does not send anything. Think of it as putting
the furniture in the room before you bring anything valuable inside.

## Creating the vault

The valuable things are your mailbox credentials, and they live in the
[[vault]]. Before downcroc can store them, the vault has to exist.

Open **vault** from the main menu and choose **init**. This is where you set
the password that protects the vault. downcroc can also remember that secret
in your system's keyring, so you do not have to type it every time, but the
vault itself is the locked store either way. Once you run it, the vault is
created and ready to be unlocked.

If you come back later and only need to open it for the day, choose
**vault** and then **unlock**. To check whether it is open or closed, choose
**status**. To close it yourself, choose **lock**. A clean stop of the daemon
locks it again on its own, so you will often see a locked [[vault]] after the
program has been off; that is normal.

> The password is the key, not the mail
>
> The vault password protects the credentials downcroc uses to sign in to
> your mailboxes. Forgetting it does not delete your mail, but it does mean
> the stored credentials cannot be opened. If that happens, you create the
> vault again and reconnect your mailboxes.

## A quick identity check

downcroc also keeps a small token that lets its own tools talk to the running
daemon. You rarely need to think about it, but it is useful to know it exists.
In the **auth** menu you can run **status** to see that the daemon and your
session agree on who is allowed to ask it for things.

With the daemon running and the vault unlocked, the ground is ready. The next
step is to give downcroc a mailbox it can send from.

⤷ every field and option on the init and vault screens:
  [../part-ii/04-vault/vault.md](../part-ii/04-vault/vault.md)
⤷ adding and connecting your first mailbox:
  [connect-a-mailbox.md](connect-a-mailbox.md)

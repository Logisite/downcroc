---
title: Turn it on
commands: [serve, service, doctor, vault.status, vault.unlock, vault.lock]
concepts: [daemon, vault]
screens: []
---

# Turn it on

downcroc does its work in the background. That means there is a moment,
before anything can be sent or watched, when you wake it up and make sure it
can reach the things it needs. This page is that moment.

## Two ways to run it

There are two ways to have the daemon running, and they feel different on
purpose.

If you choose **serve** from the main menu, downcroc runs in the foreground.
It stays attached to the window you started it in and speaks to you there.
This is the simple way to see it come up, and it is useful when you want to
watch what happens. When you stop it, it stops.

If you choose **service**, you are asking your machine to look after it for
you. The **service** menu lets you start it, stop it, restart it, and ask for
its status, and it can install itself so it comes back on its own. This is
the way you run downcroc day to day: start it once, and let it stay running
in the background while you get on with other things.

The same thing, typed: `downcroc serve` for the foreground, and
`downcroc service start` to hand it to the background.

## The lock on the door

When the daemon is running, it still cannot send mail until it can read the
credentials for your mailboxes. Those credentials live in the [[vault]], and
the vault has a lock.

A clean stop locks the vault again. That is why, after you start the daemon,
you may need to unlock the vault before anything moves. In the **vault** menu
you can check its state, unlock it, or lock it yourself. Unlocking is you
telling downcroc, for this run, that it may open the drawer where the keys
are kept. Locking puts them away.

> A normal morning looks like this
>
> The daemon is running, the [[vault]] is unlocked, and the status screen
> shows no surprises. If the daemon is stopped, the vault being locked is
> normal, not a fault.

## Asking whether it is healthy

Before you trust a quiet screen, it helps to ask the program to check itself.
Choose **doctor** from the main menu and run it. Doctor looks over the
installation and names anything that needs attention, in plain language, so
you do not have to guess.

If doctor reports a problem, it will tell you where to look. If it reports
nothing wrong, you have a solid place to stand: the daemon, the vault, and
the installation all agree.

⤷ every check doctor can report, and what each one means:
  [../part-ii/16-doctor/doctor.md](../part-ii/16-doctor/doctor.md)
⤷ the full contract of service and vault commands:
  [../part-ii/01-service/service.md](../part-ii/01-service/service.md)
⤷ creating and unlocking the vault for the first time:
  [first-run.md](first-run.md)

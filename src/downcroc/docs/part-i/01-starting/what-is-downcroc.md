---
title: What is downcroc?
commands: []
concepts: [daemon, vault, job, batch]
---

# What is downcroc?

You have a mailbox, or a few of them, and you want to send personal mail from
those addresses on a schedule you can trust. Not a newsletter blasted from
someone else's server, but messages that leave from your own accounts, at a
pace that looks like a person wrote them.

downcroc is the program that does that work for you. It runs on your machine,
in the background, and it keeps going whether or not you are looking at it.
You hand it a message, or a list of messages, and it decides when each one
should go out, which mailbox should send it, and it remembers what happened to
every single one.

## A daemon, not a website

The first word worth knowing is *daemon*. A daemon is a program that stays
running and waits for work, the way a mail room stays open through the day.
downcroc is that mail room. You can close the window you used to talk to it
and it keeps its place; you open it again later and everything is where you
left it.

Because it runs on your machine, it also keeps its things on your machine: the
list of mailboxes it can send from, the messages waiting to go out, the record
of what was sent, and the credentials that let it sign in. Those credentials
live in a locked store called the [[vault]]. When downcroc is not running, the
vault is locked, and nothing can be sent until you unlock it again.

## What it is not

It helps to be clear about what downcroc does not do, because the shape of a
tool is easier to hold when you know its edges.

It is not a website and it does not have an account somewhere else. There is
no dashboard in a browser you sign into, and nothing about your mail leaves
your machine unless you are the one sending it. It is not a marketing
platform that owns your contacts or your templates. And it is not instant: it
sends at a human pace on purpose, so a hundred messages go out over time, not
in one burst.

## The two words you will meet first

As you read on, two words will come up again and again. A [[job]] is one email
that downcroc has been asked to send, with everything it needs and a record of
what happened to it. A [[batch]] is a group of jobs you created together, so
you can look at them and steer them as one piece of work.

That is enough to hold in your head for now. The next page is about waking the
daemon up and seeing it answer.

⤷ where downcroc keeps its files and the vault on your machine: [where-is-my-stuff.md](where-is-my-stuff.md)

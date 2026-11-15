---
title: Connect a Gmail mailbox
commands: [account.add, account.connect, account.verify, provider.credentials]
concepts: [needs-reauth, vault]
screens: []
---

# Connect a Gmail mailbox

A Gmail mailbox can work with downcroc in two different ways, and the choice
you make here decides how often you will have to think about it later. Both
paths end in the same place: a connected mailbox that can send. They differ in
how you prove who you are and in how much setup they ask of you.

## The simple path: an app password

If you want the least ceremony, use an app password. In your Google account
you create a password meant for one program, and when downcroc asks you to
connect the mailbox you give it that password. downcroc stores it in the
[[vault]] and signs in the way a mail program always has. The permission lasts
until you change or remove that app password.

To do this, add the Gmail account in **account** → **add**, then choose
**connect** and provide the app password when asked. If you can create app
passwords for your account and you do not need anything beyond SMTP sending,
this is often enough.

## The OAuth path: sign in through Google

OAuth works differently. Instead of handing downcroc a password, you let Google
confirm that downcroc may act for your mailbox. This takes more steps the first
time, but it is the path Google prefers, and it is the path you need if you
want downcroc to use Gmail's API sending route.

To use OAuth with downcroc, you need an OAuth client: a small set of
credentials that identifies the application asking for permission. downcroc
lets you bring that client in as a JSON file. There are two ways to get one.

### Option A: create your own client in Google Cloud

This is the reliable path, because the client belongs to you. In a browser,
sign in to the [Google Cloud Console](https://console.cloud.google.com/) and
create a project, or pick one you already use. Inside that project, open the
APIs library and enable the
[Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com).

Next, open the [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
for the project. Google asks who the app is for and what it is called; for
your own mailbox you can set it up for yourself. This is also where the
important choice lives: while the app is in a testing state, Google only
allows the people you name as test users, and it expires their permission
often, about every seven days. To stop having to sign in again every week,
move the app out of testing and into production (publish it) for your own
use. You do not need to submit it for anyone else's review to use it with
your own account; you need it treated as a published app rather than a
temporary test.

Then open [Credentials](https://console.cloud.google.com/apis/credentials),
create an OAuth client ID, and pick the application type meant for a desktop
app. When Google creates it, download the client JSON file. That file is the
credential downcroc needs; keep it private, the same way you would keep a
password.

Now bring it into downcroc. From the main menu open **provider**, choose
**credentials**, then **set**, and point it at the JSON file you downloaded.
downcroc imports it and remembers it as an OAuth client you can use. After that,
add the Gmail mailbox in **account** → **add** (using the Gmail provider), and
run **account** → **connect**. When you connect, choose the OAuth route and,
if asked, select the client you imported. downcroc will open the browser
sign-in flow; approve access for the mailbox, and the account becomes
connected.

The same thing, typed: `downcroc provider credentials set` to import the JSON,
then `downcroc account add` and `downcroc account connect <account>`.

### Option B: use an existing desktop-app client JSON

downcroc does not require that the client JSON came from a project you just
created; it can import any compatible OAuth client JSON you are allowed to use.
Some people already have a client JSON issued for another desktop mail program
and choose to reuse it. If you go this way, import that JSON with **provider**
→ **credentials** → **set** and select it when you connect the account.

Be aware that this depends on that client's rules and on Google's policies for
it, so it can be less predictable than a client you control. If a reused client
stops working or keeps expiring, creating and publishing your own client as in
option A is the steady fix.

## When the permission expires

A Gmail mailbox that downcroc can no longer sign in to is marked
[[needs-reauth]]. The most common reason with OAuth is a client left in
testing: Google revokes the permission after about a week, and the next send
waits with that word.

Read it as a locked door, not a lost message. The address is fine and any
[[job]] waiting for it is still there. Publish the app so the permission
lasts, then open **account**, choose the mailbox, run **connect**, and finish
the sign-in again. After that, run **verify** to confirm it is healthy.

⤷ every field on the account and provider screens:
  [../part-ii/07-account/account.md](../part-ii/07-account/account.md)
⤷ importing and managing OAuth clients in detail:
  [../part-ii/06-provider/provider.md](../part-ii/06-provider/provider.md)


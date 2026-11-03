"""The only file to edit when scripting an interactive workflow.

Each story is one command plus the exact order of keys. Steps are separated by
``|``. A known key name (enter, down, up, space, esc, tab, backspace, ctrl-c)
is pressed; ``text:`` forces typing; ``pause:2`` waits; anything else is typed,
so ``/list`` filters a menu and ``acct_nope`` types a value.

    uv run python scripts/probe_stories.py --list
    uv run python scripts/probe_stories.py unarchive
    uv run python scripts/probe_stories.py --all

Add the daemon fixture with ``live=True`` when a story needs accounts, then use
``follow`` for a non-interactive command whose output proves the result.
"""

from __future__ import annotations

from probe_interactive import Story, main

STORIES = {
    "home": Story(
        name="home",
        title="root menu, account submenu, back",
        argv=[],
        live=True,
        keys="down | down | /account | enter | enter | esc | q | y",
    ),
    "account-list": Story(
        name="account-list",
        title="account list options, toggle --archived, run, back",
        argv=["account"],
        live=True,
        keys="/list | enter | o | space | r | b | q | y",
    ),
    "account-add": Story(
        name="account-add",
        title="add a mailbox, then immediately offer browser sign-in",
        argv=["account", "add"],
        live=True,
        keys="/gmail | enter | enter | probe2@example.com | enter | n",
    ),
    "account-error": Story(
        name="account-error",
        title="typed account id, failing run, retry path, back",
        argv=["account"],
        keys="/show | enter | enter | enter | acct_nope | enter | q | y",
    ),
    "send": Story(
        name="send",
        title="send leaf options, choice edit, preview, failing run",
        argv=[],
        live=True,
        keys=(
            "/send | enter | o | down | down | down | enter "
            "| down | enter | r | b | q | y"
        ),
    ),
    "help": Story(
        name="help",
        title="help topic resolver from the root tree, run a topic",
        argv=[],
        live=True,
        keys="/help | enter | enter | /vault | enter | enter | q | y",
    ),
    "vault": Story(
        name="vault",
        title="mutually exclusive pair editor and command preview",
        argv=["vault"],
        keys="/unlock | enter | o | enter | down | enter | b | q | y",
    ),
    "global-persist": Story(
        name="global-persist",
        title="a global flag stays ticked across commands",
        argv=["account"],
        keys="/list | enter | o | down | space | b | /show | enter | o | q | y",
    ),
    "provider": Story(
        name="provider",
        title="provider list and imported oauth client list",
        argv=["provider"],
        live=True,
        keys="/credentials | enter | enter | /list | enter | enter | b | q | y",
    ),
    "attempt": Story(
        name="attempt",
        title="oauth attempt shows a relative link lifetime",
        argv=["account"],
        live=True,
        keys="/attempt | enter | enter | /oauth | enter | enter | q | y",
    ),
    "unarchive": Story(
        name="unarchive",
        title="archived picker, confirm, unarchive, archived list after",
        argv=["account"],
        live=True,
        keys="/unarchive | enter | enter | enter | y | q | y",
        follow=["account list --archived"],
    ),
}


if __name__ == "__main__":
    raise SystemExit(main(STORIES))

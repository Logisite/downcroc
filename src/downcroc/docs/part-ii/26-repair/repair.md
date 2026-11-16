---
title: repair
commands: [repair]
flags: []
concepts: []
screens: []
---

# repair

## What this is for

You upgraded Python. Now `downcroc` will not start, and the error says something about an interpreter that is not executable or too many layers of symbolic links.

That is a broken [[interpreter-links]] problem. The [[repair]] command checks your [[managed-install]] and points its links at a Python that actually exists. It also checks that the [[venv]] still has downcroc in [[site-packages]].

`repair` is for a [[managed-install]], the kind created by the supported install scripts. If you made your own environment from a checkout, it will tell you so and stop.

## Before you start

The [[daemon]] must be stopped. `repair` only touches the install layout, not your mail. It does not delete your data, vault, or config.

You need a supported Python interpreter on the machine. Python 3.14 or newer is enough. If your system has none, `repair` cannot finish and will tell you what to install.

## Do it interactively

Open the command tree:

```text
downcroc
```

Choose `repair` from the list. The tree runs it and prints one status line, the detail, and the next step if there is one.

## Or run one command

```text
downcroc repair
downcroc repair --json
```

The `--json` form gives a record with `status`, `ok`, `detail`, `venv`, `base_python`, and `fix`. Use it in scripts.

## What you should see

A healthy install prints `ok`. If the links were wrong and `repair` fixed them, it prints `relinked` with the interpreter it chose.

If the install needs more work, you will see one of these:

- `needs_relink` : the links are still wrong. Run `repair` again.
- `needs_reinstall` : the interpreter works, but downcroc is not in [[site-packages]]. Run `downcroc update --force` or reinstall.
- `unrecoverable` : no supported Python was found. Install Python 3.14 or newer, then run `repair` again.

## What the words mean

A [[managed-install]] is an install the supported scripts set up, with a launcher and a private [[venv]]. The [[interpreter-links]] inside that venv are the small `python` names that point at the real Python binary. When a system upgrade removes that binary, the links dangle or loop and nothing starts. [[repair]] finds a working Python and points the links at it.

## If it goes wrong

If `repair` says `unrecoverable`, install a supported Python and run it again.

If it says `needs_reinstall`, run `downcroc update --force`. The update path also repairs links before it installs, so one command handles both.

If the daemon still will not start after a clean `repair`, read the log. Startup failures now write one `daemon.start_failed` event with the reason and the next step.

## Related

- [update](../24-update/update.md) — update a managed install
- [doctor](../16-doctor/doctor.md) — installation health check
- [uninstall](../25-uninstall/uninstall.md) — remove a managed install

---
title: Extension artifacts
commands: []
flags: []
concepts: []
screens: []
---

# Extension artifacts

An artifact is one `.pyz` file containing your extension code and its manifest.
It is the unit you build, share, install, and verify.

## What is inside

A `.pyz` is a Python zipapp. The archive root must contain:

- `__main__.py`, the entry point
- `downcroc-extension.toml`, the manifest

It may also contain other Python modules and data files. downcroc runs it with
the current Python interpreter. There is no separate virtual environment and
no dependency installer. Bundle what you need or use only the standard library
unless you control the target machine.

## Building

```sh
downcroc extension build DIR [--output PATH]
```

`DIR` must contain both required files. The default output is
`<id>-<version>.pyz` in the current directory. The command prints the output
path and its SHA-256:

```json
{"path": "/tmp/reply-bot-1.0.0.pyz", "sha256": "9f2c..."}
```

Share both the file and the checksum if you send it to someone else.

## Installing

```sh
downcroc extension add reply-bot.pyz
```

The installer:

1. reads `downcroc-extension.toml` from the archive
2. validates the manifest
3. computes the artifact SHA-256
4. copies the file to `extensions/artifacts/` under your config home
5. writes a derived manifest at `extensions/<id>.toml`
6. reloads the extension host

The extension is installed but not enabled. Enable it when you are ready:

```sh
downcroc extension enable reply-bot
```

`extension add` still accepts a plain `.toml` manifest. That path is unchanged
and is useful during development when you want to edit code in place.

## Verifying

```sh
downcroc extension verify reply-bot --json
```

The command recomputes the SHA-256 and compares it with the value recorded at
install time. It returns:

```json
{"extension": "reply-bot", "kind": "pyz", "verified": true}
```

A `false` value means the installed file changed. The host performs the same
check before every launch and every one-shot test. A missing or changed file
logs `extension.artifact_invalid` and no extension code runs.

`extension show` reports the artifact path and the last verification result.

## What the checksum means

The checksum proves the installed file is the same file you added. It does not
prove the author is trustworthy. It does not sandbox the code. It does not
replace capability grants or elevated approval.

Treat a checksum from an author as a way to confirm you received the file they
intended to send. Treat the capability grants as the real security boundary.

## Replacing an artifact

Build a new version with a new `version` in the manifest, then add it again. If
you reuse the same id and version, the installer replaces the existing artifact
and manifest. That invalidates any elevated approval because the manifest
digest changes.

After replacing an artifact, reload the host:

```sh
downcroc extension reload
```

If the extension was elevated, approve it again.

## Removing

There is no dedicated remove command in this release. Disable the extension,
then delete its manifest and artifact from the config directory if you no
longer want it:

```sh
downcroc extension disable reply-bot
downcroc extension reload
```

Keep a copy of the artifact if you may want to install it again later.

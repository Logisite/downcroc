---
title: Extension events
commands: []
flags: []
concepts: []
screens: []
---

# Extension events

When you want to know what an extension did, you read the daemon log. This is
the same log you use for every other part of downcroc, and
`downcroc extension logs ID` filters it to one extension for you. The complete
field-by-field reference lives in
[Extension log events](../19-logs/events/extensions.md).

The short version is this. `extension.started` says the daemon accepted the
manifest and launched the process. `extension.call` says a capability ran and
records how long it took. `extension.denied` says the extension asked for
something it was not granted. `extension.call_failed` says the call was allowed
but failed while running. `extension.crashed` and `extension.timeout` say the
host had to restart it. `extension.stopped` closes the story when you disable
it or the daemon shuts down.

Read them in id order. A healthy extension has a start, a run of calls, and a
stop when you turn it off. A restart shows up as a crash or timeout followed by
another start. If a capability you expected is missing, check the manifest's
events and the config's `allow` list before reading anything else.

No event in this family contains a credential. That is the boundary the whole
extension system is built around, and the log is where you can confirm it held.

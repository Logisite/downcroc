---
term: daemon
see_also: [vault]
---

The background process that owns downcroc’s state and does the work: sending,
watching, syncing, and serving the local API. The CLI talks to the daemon; when
it is not running, nothing moves. Starting it does not unlock the [[vault]].

More: [service](../part-ii/01-service/service.md), [serve](../part-ii/01-service/serve.md), [status](../part-ii/02-status/status.md)

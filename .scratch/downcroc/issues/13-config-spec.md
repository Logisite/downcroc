# 13 - Config and spec without a restart

**What to build:** configuration has one schema with defaults, ranges and descriptions, exposed
through the API. A patch is validated, written atomically and picked up by running services with
no restart. A bad value is rejected and leaves the file alone. `downcroc openapi` writes
`openapi.json` from the live app so the document and the daemon cannot disagree.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] the schema endpoint lists every field with type, default, range and description
- [ ] patching the jitter takes effect on the next send without a restart
- [ ] an out-of-range value is rejected with the field name and the file is unchanged
- [ ] a config file edited by hand is reloaded and the running values follow
- [ ] a malformed file is reported and the previous values stay active
- [ ] `downcroc openapi` writes a document identical to the served `/openapi.json`

**Logs:** the events this ticket introduces.

- `config.loaded` path, keys
- `config.reloaded` changed
- `config.rejected` field, reason
- `openapi.exported` path, routes

**Commit:** `feat(config): add schema, hot reload, openapi export`

# 02 - State that survives, changes that announce themselves

**What to build:** the database exists, migrations run at startup, and accounts can be created,
listed and removed through the API in `pending` state, surviving restart. Every mutation emits an
event with a sequence number on a stream a client can subscribe to, replay from, and detect a gap
in. Accounts carry their weight and policy fields from the start.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] migrations run at startup on an empty directory and again on an existing one without changes
- [ ] create, list, get and delete an account through the API, and all of it survives a restart
- [ ] deleting an account that jobs reference is refused with a clear code
- [ ] creating an account emits an event carrying its id, no object bodies
- [ ] a subscriber that drops and reconnects with `Last-Event-ID` receives the missed events
- [ ] a `Last-Event-ID` older than the ring produces one `gap` event, not silence
- [ ] the stream stays useful while the daemon is idle

**Logs:** the events this ticket introduces.

- `db.migrate` from, to, duration_ms
- `account.created`, `account.updated`, `account.deleted` account id
- `sse.connected` client, last_event_id
- `sse.disconnected` reason
- `event.gap` requested_id, oldest_id

**Commit:** `feat(state): add accounts schema, event stream`

# 01 - The daemon shell that answers

**What to build:** the first run creates and validates `config.toml`, creates the XDG directories
with the right permissions, sets up the log, takes a single instance lock, writes `service.json`,
and serves `/api/health` and `/api/status` on loopback. The CLI can start it detached, report
status, stop it, query the log, and dump the OpenAPI document. Logging lands here: one JSON line
per event to a rotating file, a pretty colour rendering on a terminal, and `downcroc logs` to
filter either view. There is no database yet.

**Blocked by:** None, can start immediately.

**Status:** in progress

- [ ] empty HOME: `downcroc serve` creates config, dirs and log, and health reports version and uptime
- [ ] `service start` detaches, `status` reports pid, port and uptime, `stop` exits and removes `service.json`
- [ ] a second start is refused and names the running pid
- [ ] an invalid config value is rejected with the field name and nothing is written
- [ ] a host other than loopback is refused
- [ ] a killed daemon leaves no stale lock that blocks the next start
- [ ] `downcroc openapi` prints a valid document
- [ ] a log line is one JSON object with `ts`, `level`, `event` and its fields
- [ ] `downcroc logs` renders aligned colour columns, and `--json` prints the raw lines

**Logs:** the events this ticket introduces.

- `daemon.start` version, pid, port, config path
- `daemon.ready` port, boot_ms
- `daemon.stopping` signal, uptime_s
- `config.loaded` path, keys
- `config.invalid` field, reason
- `lock.acquired` path
- `lock.refused` pid, port

**Commit:** `feat(shell): add config, paths, lock, logging, health route`

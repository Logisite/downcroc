# 01 - Portable daemon lifecycle on Linux and Windows

**What to build:** the daemon starts, reports status, and stops cleanly on Linux and Windows. Resolve platform-specific config, data, state, and log directories while preserving XDG overrides. Replace Unix-only instance locking and process liveness checks with portable equivalents. Make detached start, graceful shutdown, restore shutdown, and permission handling work on both systems. Introduce a per-run control token for authenticated shutdown as a prefactor for full API authentication in ticket 03. Run the complete acceptance suite in a two-OS GitHub Actions matrix. Update the architecture and module decision records for the platform boundary. macOS is out of scope: no CI leg, no artifact, no support commitment.

**Blocked by:** None. Can start immediately.

**Status:** ready-for-agent

- [ ] An empty home directory starts the daemon, creates config and directories with safe permissions, writes the log, and serves health and status on loopback
- [ ] `service start`, `service status`, and `service stop` work on Linux and Windows
- [ ] Stop runs the application shutdown path, locks the vault, removes `service.json`, and leaves no stale lock
- [ ] A second start is refused and names the running process
- [ ] A killed daemon does not leave a lock that blocks the next start
- [ ] Detached start and process liveness do not depend on Unix-only system calls
- [ ] An invalid config value is rejected with the field name and no partial state is written
- [ ] A host other than loopback is refused
- [ ] Shutdown through the control token requires the token and works on every supported system
- [ ] The full test suite is green on Linux and Windows in GitHub Actions
- [ ] No local build, packaging, or binary step is added to the developer workflow
- [ ] Architecture and module decision records describe the portable lifecycle

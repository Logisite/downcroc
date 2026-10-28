# 05 - User service installation

**What to build:** `downcroc service install` and `downcroc service uninstall` create and remove native user services on Linux and Windows. Linux uses a systemd user unit and Windows uses a scheduled task that runs at logon. Generated service definitions use absolute binary paths and the correct user environment, logs, and working directory. Installation is idempotent, does not require root or administrator rights, and preserves data on uninstall. macOS is out of scope.

**Blocked by:** 01 - Portable daemon lifecycle on Linux and Windows.

**Status:** ready-for-agent

- [ ] Linux install writes a systemd user unit, reloads the user manager, enables the unit, and starts the daemon
- [ ] Linux uninstall stops and disables the unit, removes the unit file, and preserves config, state, and data
- [ ] Windows install registers a scheduled task that starts the daemon at logon
- [ ] Windows uninstall removes the task while preserving user data
- [ ] Re-running install updates the absolute binary path without creating duplicate services
- [ ] Installation and uninstallation do not require root or administrator rights
- [ ] Generated systemd unit and task definitions are checked in CI
- [ ] Actual service registration passes manual smoke checks on each supported system before the first release
- [ ] The command is included in the binary build in ticket 06

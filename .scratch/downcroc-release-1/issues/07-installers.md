# 07 - Installers, updater, and uninstallers

**What to build:** `install.sh` for Linux and `install.ps1` for Windows. Each installer downloads a matching release archive, verifies its checksum, installs under a stable user prefix, adds one `downcroc` entry to the user PATH, and keeps that global path current on later upgrades. Add `downcroc update` with `--check`, `--pre`, and `--force`. It checks the GitHub release feed, verifies checksums and attestations, downloads the matching archive, replaces the installed tree atomically where the platform allows, refreshes the global PATH entry and any installed user service, preserves config, state, and data, and prints release notes. Provide matching uninstallers that remove the binary and PATH entry while preserving data. An explicit purge option removes everything. Installation never invokes `sudo` or administrator elevation automatically. Test install, upgrade, update, uninstall, and data preservation in GitHub Actions against staged binary artifacts. macOS is out of scope.

**Blocked by:** 06 - Cross-platform binary artifacts.

**Status:** ready-for-agent

- [ ] `install.sh` installs a staged Linux artifact and `downcroc --version` works after PATH refresh
- [ ] `install.ps1` installs a staged Windows artifact and `downcroc --version` works after PATH refresh
- [ ] Re-running an installer upgrades an existing install in place, keeps exactly one PATH entry, and preserves config, state, data, and service registration
- [ ] The installed archive has one stable global launcher path per operating system and the PATH entry points at it, not at a versioned directory
- [ ] `downcroc update --check` reports current and latest versions and release notes without downloading or changing anything
- [ ] `downcroc update` replaces the installed tree, refreshes the global launcher and PATH entry, updates the installed user service to the new absolute path, and preserves data
- [ ] `downcroc update --pre` can move to a newer pre-release and the default channel only moves to a stable release
- [ ] `downcroc update --force` reinstalls the current version and refuses downgrades without it
- [ ] A checksum or attestation failure aborts installation or update without changing the running global launcher
- [ ] Update refuses to replace an installation it does not own or cannot verify
- [ ] Uninstall removes the binary and PATH entry and preserves config, state, and data
- [ ] A documented purge option removes config, state, and data without prompting for confirmation beyond the explicit flag
- [ ] No automatic `sudo` or administrator elevation occurs
- [ ] CI runs install, upgrade, update, version, service path refresh, uninstall, and data-preservation checks on Linux and Windows
- [ ] Installer and updater output never prints credentials or daemon tokens

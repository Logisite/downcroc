# 06 - Cross-platform binary artifacts

**What to build:** onedir binaries for Linux and Windows, built only in GitHub Actions. Each binary contains the daemon, CLI, authentication, service installation, self-update command, migrations, provider declarations, and the packaged documentation book. Start with a CI-only freeze spike to prove that the chosen freezer supports the project on every target, then produce the final artifacts. Include the optional OS credential-store backend so `vault keyring` works from the frozen binary and degrades to the password prompt when the backend is absent. Run a binary smoke test on each operating system and upload the artifacts for the release pipeline. macOS is out of scope.

**Blocked by:** 01 - Portable daemon lifecycle on Linux and Windows, 02 - Installable wheel with Apache 2.0 metadata, 03 - Authenticated daemon API and CLI, 04 - Unified product documentation and terminal access, and 05 - User service installation.

**Status:** ready-for-agent

- [ ] A CI-only spike proves the freezer can build and start the daemon on Linux and Windows
- [ ] Each operating system produces a self-contained onedir artifact
- [ ] The artifact contains migrations, provider declarations, licensing, notices, and the packaged documentation book
- [ ] `downcroc --version` reports the release version
- [ ] `downcroc docs --list` reads the packaged book
- [ ] `service start`, health, authenticated API access, `vault unlock`, and `service stop` work from the artifact
- [ ] `vault keyring status` answers from the artifact, and `vault unlock` falls back to the password prompt when no credential store is present
- [ ] The service installation command is present and can generate its platform service definition
- [ ] The `downcroc update --check` command is present and runs from the artifact without changing the installation
- [ ] The binary smoke test runs on the matching operating system and fails the build on any failure
- [ ] Artifacts are uploaded with deterministic names for the release workflow
- [ ] No local binary build is required or documented as the release path

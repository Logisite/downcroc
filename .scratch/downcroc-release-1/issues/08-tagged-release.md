# 08 - Tagged 1.0 release pipeline

**What to build:** annotated and protected tags `v1.0.0-rc.1` and `v1.0.0` trigger the release workflow. Verify that the tag matches the package version. Call the reusable CI and binary build workflows, generate checksums and build attestations, create a draft release with notes and installers, and publish only after approval. Run post-release install and self-update tests against the published assets on Linux and Windows. Produce release notes from the changelog, state what changed, and keep the release CLI-only. macOS is out of scope.

**Blocked by:** 06 - Cross-platform binary artifacts, and 07 - Installers and uninstallers.

**Status:** ready-for-agent

- [ ] A tag that does not match the package version fails before any artifact is published
- [ ] `v1.0.0-rc.1` produces a complete release candidate with binaries, installers, checksums, attestations, and release notes
- [ ] The release candidate installs and starts successfully on Linux and Windows
- [ ] `v1.0.0` produces the final release from the same workflow
- [ ] Checksums cover every published artifact and are attached to the release
- [ ] Build attestations cover every published binary
- [ ] The draft release is reviewed before publishing
- [ ] Post-release install, version, daemon start, authenticated API access, service stop, and uninstall checks pass on both systems
- [ ] Post-release `downcroc update` from `v1.0.0-rc.1` to `v1.0.0` refreshes the global launcher, updates the installed service path, preserves data, and prints the feature notes on both systems
- [ ] Release notes state that the product is CLI-only, that the API uses a local bearer token, and how to update an existing install
- [ ] No local release, binary, docs, or installer build is required

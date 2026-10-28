# 02 - Installable wheel with Apache 2.0 metadata

**What to build:** a wheel that installs outside the repository and runs the daemon without relying on repository-root files. Package database migrations, provider declarations, and runtime resources, and load migrations from packaged resources. Make the installed package report the correct version. Add Apache 2.0 licensing, notices, and complete project metadata. Build and smoke-test the wheel only in GitHub Actions on Linux and Windows.

**Blocked by:** 01 - Portable daemon lifecycle on Linux and Windows.

**Status:** ready-for-agent

- [ ] CI builds a wheel from the tagged or current source and installs it into a clean environment on Linux and Windows
- [ ] The installed `downcroc --version` matches the package version
- [ ] The installed daemon creates config and state, runs every migration, and reports healthy
- [ ] Migrations and provider declarations are present in the wheel and do not depend on the repository root
- [ ] Apache 2.0 `LICENSE` and `NOTICE` are included in the wheel and source distribution
- [ ] Package metadata declares Apache 2.0, the project URLs, the Python requirement, and the console entry point
- [ ] Third-party licence information is available from the installed package or its distribution metadata
- [ ] The wheel smoke test starts and stops the daemon on every supported system
- [ ] `uv lock --check`, Ruff, formatting, and compile checks pass in CI
- [ ] No local wheel build or install step is added to the developer workflow

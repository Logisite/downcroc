# 04 - Unified product documentation and terminal access

**What to build:** one product documentation book for the application and its CLI. It contains Getting started, Concepts, Operations, CLI usage, Reference, Security, Troubleshooting, and Release notes. CLI usage is a section of the book, not a separate CLI-only manual. There is no GUI documentation. Build the book in CI, publish it to GitHub Pages, package it in the wheel, and expose it through `downcroc docs` with topic lookup, listing, search, open, and raw output. Update the README, changelog, and security policy. The terminal command is a delivery surface for the same book, not a second documentation set.

**Blocked by:** 02 - Installable wheel with Apache 2.0 metadata, and 03 - Authenticated daemon API and CLI.

**Status:** ready-for-agent

- [ ] The docs build in GitHub Actions with a link check
- [ ] The book covers installation, first run, vault, accounts, inbound mail, outbound mail, intake, dispatch, replies, follow-ups, batches, jobs, statistics, retention, backup, restore, configuration, providers, security, troubleshooting, and release notes
- [ ] CLI usage is a clearly marked section with every command and common workflow
- [ ] There is no GUI section and no browser login documentation
- [ ] `downcroc docs --list`, `downcroc docs <topic>`, `--search`, `--open`, and `--raw` work from an installed wheel
- [ ] The packaged book is present in the wheel and opens without network access
- [ ] GitHub Pages deploys the same book from the main branch
- [ ] The README covers wheel install, binary install, source install, daemon auth, and the CLI-only scope
- [ ] A changelog and security policy exist and follow the project conventions
- [ ] Documentation reflects authenticated API access and the absence of a web GUI

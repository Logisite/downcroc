# 12 - Module map

## The rule

One external library, one home. One direction of dependency. Every cross module call goes through
a protocol in `ports/`, never through a concrete class.

```
cli / tui / api            entry points, one per client surface
        |
      core                services, orchestration, every rule
        |
   ports (protocols)      the only things core may name
        |
   domain                pure types and rules, no I/O
        |
 adapters                store, vault, providers, mail, html, backup
```

`core` imports `ports` and `domain` and nothing else. Concrete adapters are wired at a single
composition root, `core/bootstrap/`, so a script or a workstation can substitute a stub IMAP
without importing `imap-tools` at all.

## Top level

| Module | Owns | May import |
|---|---|---|
| `ports` | every protocol between layers | typing only |
| `domain` | entities, states, value objects, error codes | nothing |
| `store` | SQLite, migrations, repositories, content store, search | `domain` |
| `vault` | Argon2id, AES-GCM, the credential file | `domain` |
| `providers` | declarations, OAuth, token refresh, XOAUTH2 | `domain`, `ports` |
| `mail` | SMTP, IMAP, MIME, Message-ID minting | `domain`, `ports` |
| `html` | sanitize for display, inline CSS for send | nothing |
| `core` | services and workflows | `domain`, `ports` |
| `api` | routes, SSE, error envelope | `core`, `domain` |
| `tui` | Textual app, screens, widgets, API client | the API contract only |
| `backup` | bundle create, verify, restore | `store`, `vault`, `domain` |
| `runtime` | config, paths, logging, service control, clock, ids | `domain` |
| `cli` | command surface and daemon control | `core`, `api`, `tui`, `runtime` |

## The tree

```
downcroc/
  ports/
    repositories.py     AccountRepo BatchRepo JobRepo MessageRepo ThreadRepo
                        AttachmentRepo AttemptRepo QuotaRepo CounterRepo
                        EventRepo FailureRepo
    secrets.py          SecretStore
    content.py          ContentStore
    mail.py             Sender Receiver
    providers.py        ProviderResolver ProviderSpec
    events.py           EventSink EventStream
    time.py             Clock
    ids.py              IdGenerator

  domain/
    accounts.py         Account AccountStatus SendPolicy QuotaState
    jobs.py             Job JobState Attempt FailureReason
    batches.py          Batch BatchState BatchOptions SnapshotRef
    messages.py         Message Address Headers ReplyState DsnInfo
    threads.py          Thread ThreadLink Relation
    templates.py        TemplateSpec VariableSpec RenderResult
    stats.py            counter definitions, the exact meaning of each number
    events.py           EventType Event
    attempts.py         ConnectAttempt AttemptState
    providers.py        ProviderSpec AuthKind TlsMode
    secrets.py          secret kinds and key naming
    errors.py           stable machine codes
    suppression.py      the suppression rule
    validators.py       address syntax, dedupe, variable coverage

  store/
    db/
      engine.py         engine, session factory, WAL pragmas
      migrate.py        packaged Alembic config and upgrade
      migrations/       env.py, script.py.mako, versions/
      models/           SQLAlchemy declarative models
        accounts.py jobs.py batches.py messages.py threads.py
        attempts.py counters.py events.py failures.py
    repositories/       session queries, returning domain objects
      accounts.py account_state.py batches.py jobs.py messages.py
      threads.py attachments.py attempts.py quota.py counters.py
      events.py failures.py
    content/
      layout.py         path scheme and path validation
      files.py          put, get, open, delete, hash
      blobs.py          copy a file into the store
    search.py           FTS5 over message bodies

  vault/
    kdf.py              Argon2id parameters, bounded tuning, derive
    format.py           header encode and decode, digest, magic, version
    cipher.py           AES-256-GCM, authenticated header
    store.py            atomic replace, fsync, temporary file cleanup
    secrets.py          key naming, secret records, cbor map

  providers/
    registry.py         built ins plus user overrides, declaration validation
    declarations/       gmail.toml microsoft.toml generic.toml
    oauth/
      flow.py           attempt lifecycle, loopback listener, state nonce
      client.py         authorize and token calls
      pkce.py
    token.py            refresh, cached access token, per account lock
    xoauth2.py          builds the SASL string, kept for the SMTP path

  mail/
    mime/
      builder.py        multipart alternative, mixed, headers, message-id minting
    smtp/
      sender.py         aiosmtplib session, mechanism choice, error mapping
    imap/
      connection.py     imap-tools session, XOAUTH2 or app password
      client.py         search, fetch, idle primitives
      folders.py        INBOX and sent folder probing

  html/
    sanitize.py         nh3, for rendering received mail
    inline.py           css-inline, for sending

  core/
    bootstrap/
      __init__.py       build and the Services facade
      build.py          composition order
      foundation.py     storage, repos, vault, policy, providers, stats
      services.py       the wired service set
      inbound.py transports.py accounts.py outbound.py scheduling.py
      failures.py operations.py dispatch.py support.py
    events.py           event bus, sequence, ring buffer writer
    vault/
      __init__.py       the vault facade
      service.py        unlock, lock, throttle, secret access, token cache
      file.py           sealed envelope, atomic writes, permissions
      prune.py          orphan pruning and unlock credential checks
      ports.py          the narrow account directory the vault slice needs
      credentials/presence.py  vault-backed credential presence
    accounts/
      __init__.py       the account facade
      service.py        connect, verify, disable, reauth handling
      login.py          IMAP login, OAuth exchange, health transitions
      lifecycle.py      archive and unarchive state transitions
      watcher.py        watcher enable and disable port
      eligibility.py    one routing, dispatch, and seat eligibility rule
      preflight.py      background credential check after unlock
    outbound/
      service.py        send one job through the selected transport
      attempts/
        recorder.py     one attempt per delivery try, idempotent finalize
        quota.py        reserve, commit, and release quota
        reconcile.py    close stale attempts at startup
      jobs/
        create.py       manual field validation, batch sentinel, sender checks
        manual.py       create one ad-hoc job, choose the mailbox
        facade.py       job list, count, get, create, and hold scope
      credentials.py    resolve oauth or app password send credentials
      reconcile.py      reconcile a crashed send against the sent folder
    batches/
      service.py        submit, approve, cancel, list
      source.py         detect, parse, and template a source
      builder.py        materialise jobs and MIME payloads
      snapshot.py       canonical campaign snapshot
      samples.py        sample selection and stored sample previews
    jobs_service.py     lease, requeue, reassign, cancel, retry
    templates_service.py list, read, preview, edit through $EDITOR
    stats_service.py    counter increments, rollups, rebuild
    retention.py        every pruning policy
    followups/
      service.py        facade for planning, declarations, and status
      catalog.py        snapshot and declaration catalog
      declaration.py    shared and payload declaration model
      declaration_builder.py  validation and row construction
      declaration_service.py  declare, remove, retire, versioning
      immediate.py      immediate payload follow-up path
      payload.py        payload matching and content storage
      planning.py       per-parent and per-step planning
      sender.py         actual parent sender resolution
      status.py         derived step status
      status_service.py status API and CLI view
      threading.py      parent chain and child headers
    routing.py          fixed and weighted account assignment, recorded once
    inputs/
      detector.py       which format a file is
      campaign_input.py JSON campaign entry and reference checks
      campaign_message.py message fields, overrides, attachments
      campaign_policy.py routing and campaign options
      campaign_followup.py follow-up step fields
      field_input.py    shared field validation
      csv_input.py      rows and headers
      normalizer.py     the Campaign and Message records both produce
    rendering/
      loader.py         read a template directory
      renderer.py       variable substitution
      assets.py         template assets and inline image references
    dispatch/
      service.py        tick loop, weighted pick, leases, retries, batch completion
      eligibility.py    local day, window, status checks
      failures.py       failed.jsonl, failure table, retry, startup reconcile
      retry.py          exponential backoff with jitter
    inbound/
      service.py        supervision, reconcile, watcher lifecycle
      watcher.py        per account thread, IMAP sync, idle and poll
      worker.py         queue worker: ingest, cursor, watcher state
      signals.py        queue items, handles, watcher errors
      classifier.py     DSN detection and parsing
      threader.py       header based linking
      attribution.py    confirmed, probable, job attribution
      suppression.py    suppression index and queries

  api/
    app.py              app factory, lifespan, routers, disabled public docs
    auth.py             bearer token and Host/Origin middleware
    deps.py             pulls services from the composition root
    errors.py           error envelope, code to HTTP mapping
    sse.py              stream, Last-Event-ID replay, gap detection
    schemas/            request and response models per resource
    routes/
      health.py service.py vault.py accounts.py attempts.py providers.py batches.py
      jobs.py messages.py threads.py stats.py failed.py config.py backups.py
      events.py

  tui/
    app.py              Textual app, screen registry, bindings
    theme.py            one accent, light and dark terminal safe
    keys.py             binding table and help text
    approval.py         the five sample modal state machine
    client/
      api_client.py     httpx async
      sse.py            event stream with resume
      state.py          client side cache
    widgets/
      account_rail.py stat_line.py table.py sparkline.py banner.py
      empty_state.py
    screens/
      overview.py batches.py batch_detail.py accounts.py mailbox.py
      threads.py failures.py templates.py settings.py stats.py logs.py
      approval.py

  backup/
    bundle.py           create and read the archive
    manifest.py         manifest schema, hashing, version stamps
    db_snapshot.py      sqlite backup API copy
    verify.py           hash verification and schema comparison
    restore.py          staging, rename swap, refusal rules
    pending.py          the restore pending marker

  runtime/
    clock.py            Clock, SystemClock, FakeClock
    ids.py              prefixed id generation
    fs.py               permission, directory sync, atomic write helpers
    paths.py            XDG and Windows directories and permissions
    keyring.py          optional OS credential store adapter for the vault password
    logging/
      setup.py          sinks, rotation, level from config
      format.py         the JSONL formatter and the pretty one
      redaction.py      credential scrubbing at the boundary
      context.py        correlation ids: job, batch, account, attempt
    config/
      schema.py         every field with default, range, description
      loader.py         read, merge, validate
      store.py          atomic write and hot reload
    service/
      registry.py       service.json
      process.py        liveness, terminate, kill, detached process flags
      token.py          per-run bearer token
      lock.py           single instance lock on POSIX and Windows
      lifecycle.py      start, stop, status, foreground serve
      units.py          systemd and scheduled task definitions
      install.py        native user service install and uninstall

  cli/
    main.py             dispatch, error reporting, exit codes
    parser.py           argparse surface and subcommands
    client.py           loopback HTTP client and API errors
    context.py          paths and config loading
    output.py           tables, records, JSON, colour detection
    ui/
      edit.py           line editor, visible caret, tab completion
      complete.py       filesystem-only path completion
      auth.py           credential preflight status strip
    commands/
      serve.py service.py openapi.py auth.py vault.py accounts.py batches.py jobs.py
      failed.py config.py stats.py mail.py backup.py restore.py logs.py
```

## The seams

`alembic.ini` at the repo root is a developer convenience. The migrations themselves live in
`store/db/migrations/` inside the package, so a wheel carries them and runtime never reads a
repository-root file. The models they generate from live in `store/db/models/`, so the schema
has exactly one definition.

| Protocol | Real implementation | Local substitute |
|---|---|---|
| `Sender` | `mail/smtp/sender.py` | records messages, returns scripted codes |
| `Receiver` | `mail/imap/client.py` | scripted mailbox with UIDVALIDITY changes |
| `SecretStore` | `core/vault/service.py` | in-memory dict |
| `ContentStore` | `store/content/files.py` | temp directory |
| `ProviderResolver` | `providers/registry.py` | fixed specs |
| `EventSink` | `store/repositories/events.py` | list collector |
| `Clock` | `runtime/clock.py` | `FakeClock`, so windows and midnights can be exercised without waiting |
| repositories | `store/repositories/*` | not needed, SQLite in a temp file is enough |

The substitutes exist so a script or a person can drive a workflow without a provider account.
They are not a test harness.

## One library, one home

| Library | Allowed only in |
|---|---|
| `fastapi`, `uvicorn`, `pydantic` | `api` |
| `textual` | `tui` |
| `aiosmtplib` | `mail/smtp` |
| `imap-tools` | `mail/imap` |
| `argon2-cffi`, `cryptography`, `cbor2` | `vault` |
| `sqlalchemy`, `alembic`, `sqlite3` | `store` |
| `httpx` | `providers/oauth`, `tui/client` |
| `nh3`, `css-inline` | `html` |
| `tomllib`, `tomli-w` | `runtime/config` |
| `zstandard` | `backup` |

If a second module needs one of these, it goes through a port. That is the enforcement mechanism,
and it is one import linter rule per row.

## Where a new thing goes

| New thing | Touches | Does not touch |
|---|---|---|
| A provider with OAuth | a declaration file, plus an adapter only if its auth differs | queue, API, TUI |
| A provider with an app password | a declaration file | anything else |
| A new input format | `core/inputs/detector.py` and a parser | jobs, dispatch, API |
| A new report | `core/stats_service.py`, one route, one screen | the send path |
| A new send transport | a `Sender` implementation in `mail/` | core, API, TUI |
| A new client | a package against the OpenAPI document | daemon internals |
| A new retention policy | `core/retention.py` | everything else |

If a change requires editing both `dispatch/` and `api/`, the boundary is wrong and the design
should be fixed before the code is written.

## Test tree

`tests/` is the black-box acceptance suite. It starts the real daemon and drives it over
loopback HTTP, real SQLite storage, and the real JSONL log. Only external SMTP, IMAP, and OAuth
servers are faked. `tests/harness/` owns process startup, API helpers, and the fakes; one file
per feature area sits beside it. `tests/wheel_smoke.py` checks an installed wheel and its
artifacts.

Run only the affected file while working, and the full suite once at the end. Authentication and
token-leak coverage lives in `tests/test_api_auth.py` and `tests/test_auth_leaks.py`.

## Which modules land in which build phase

| Phase | Modules |
|---|---|
| P0 | `runtime`, `store/db`, `api/app`, `api/routes/health`, `cli`, a TUI shell |
| P1 | `vault`, `store/repositories/accounts`, `core/events`, `core/accounts`, `api/routes/accounts`, `api/routes/events`, `providers/registry`, `providers/declarations`, `providers/oauth`, `providers/token`, `mail/imap/connection`, `api/routes/providers`, `api/routes/attempts` |
| P2 | `core/inbound`, `store/repositories/messages`, `store/content`, `mail/imap`, `tui/screens/mailbox` |
| P3 | `mail/mime`, `mail/smtp` |
| P4 | `core/inputs`, `core/rendering`, `core/batches`, `core/dispatch`, `core/retry`, `core/failures_service` |
| P5 | `core/inbound/threader`, `classifier`, `attribution`, `suppression`, `core/followups`, `core/stats_service` |
| P6 | `core/retention`, `backup`, `runtime/config/store`, `runtime/service`, reconciliation in `core/bootstrap` |
| P7 | `tui` in full, `api/schemas`, `api/sse`, `runtime/logging` |

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
composition root, `core/bootstrap.py`, so a script or a workstation can substitute a stub IMAP
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
    bootstrap.py        composition root, wires adapters into services
    events.py           event bus, sequence, ring buffer writer
    vault_service.py    unlock, lock, throttle, secret access, token cache
    vault_file.py       sealed envelope, atomic writes, permissions
    accounts_service.py connect, verify, disable, reauth handling
    outbound/
      service.py        build a job and send it
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
    followups.py        sequence planning, due steps, eligibility, thread headers
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
    app.py              app factory, lifespan, routers
    deps.py             pulls services from the composition root
    errors.py           error envelope, code to HTTP mapping
    sse.py              stream, Last-Event-ID replay, gap detection
    schemas/            request and response models per resource
    routes/
      health.py vault.py accounts.py attempts.py providers.py batches.py
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
    paths.py            XDG directories and permissions
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
      lock.py           single instance lock
      lifecycle.py      start, stop, status, foreground serve

  cli/
    main.py             argument parsing, subcommands
    attach.py           discover the daemon, start it if needed, attach the TUI
    commands/
      serve.py service.py send.py account.py stats.py backup.py restore.py logs.py
```

## The seams

`alembic.ini` and `migrations/` sit at the repo root, the way the Alembic docs lay them out. The
models they generate from live in `store/db/models/`, so the schema has exactly one definition.

| Protocol | Real implementation | Local substitute |
|---|---|---|
| `Sender` | `mail/smtp/sender.py` | records messages, returns scripted codes |
| `Receiver` | `mail/imap/client.py` | scripted mailbox with UIDVALIDITY changes |
| `SecretStore` | `core/vault_service.py` | in-memory dict |
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

## No test tree

There is no `tests/` package and no test framework. Verification is live: run the daemon, use it,
watch what happens. `scripts/` holds throwaway setup tools (seed a mailbox, generate a 1,000-row
CSV) that print their output and assert nothing. If one piece of logic is genuinely hard to
observe live, a self-check script printing a table is acceptable, and it is never wired into a
build.

## Which modules land in which build phase

| Phase | Modules |
|---|---|
| P0 | `runtime`, `store/db`, `api/app`, `api/routes/health`, `cli`, a TUI shell |
| P1 | `vault`, `store/repositories/accounts`, `core/events`, `core/accounts_service`, `api/routes/accounts`, `api/routes/events`, `providers/registry`, `providers/declarations`, `providers/oauth`, `providers/token`, `mail/imap/connection`, `api/routes/providers`, `api/routes/attempts` |
| P2 | `core/inbound`, `store/repositories/messages`, `store/content`, `mail/imap`, `tui/screens/mailbox` |
| P3 | `mail/mime`, `mail/smtp` |
| P4 | `core/inputs`, `core/rendering`, `core/batches`, `core/dispatch`, `core/retry`, `core/failures_service` |
| P5 | `core/inbound/threader`, `classifier`, `attribution`, `suppression`, `core/followups`, `core/stats_service` |
| P6 | `core/retention`, `backup`, `runtime/config/store`, `runtime/service`, reconciliation in `core/bootstrap` |
| P7 | `tui` in full, `api/schemas`, `api/sse`, `runtime/logging` |

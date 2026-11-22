---
title: Configuration reference
commands: []
flags: []
concepts: []
screens: []
---

# Configuration reference

This page documents the fields in downcroc’s configuration (`config.toml`) and their meaning. To see every supported field from your installed version, run `downcroc config schema` (and `downcroc config show` for the effective values). You can change fields with `downcroc config set` (see [Part II: config](../part-ii/17-config/config.md)).

Values shown here are the built-in defaults and constraints defined by the application. Some fields require a daemon restart to take effect; `config schema` and `config set` report when a change requires `downcroc service restart`. The daemon binds its API to loopback only.

## daemon

HTTP daemon settings.

- `daemon.host` (default `127.0.0.1`, restart required): Loopback address the HTTP API binds to. Must be a loopback address.
- `daemon.port` (default `8765`, 1024–65535, restart required): TCP port for the HTTP API.
- `daemon.start_timeout_s` (default `60.0`, >0, ≤120): Seconds to wait for a detached daemon to become healthy.
- `daemon.stop_timeout_s` (default `15.0`, >0, ≤120): Seconds to wait for a daemon to stop before killing it.

## logging

Daemon log settings.

- `logging.level` (default `info`, one of `debug|info|warning|error`): Minimum log level written to the daemon log.
- `logging.max_bytes` (default `10485760`, ≥65536, restart required): Maximum size of one log file before rotation.
- `logging.backups` (default `5`, 1–50, restart required): Number of rotated log files to keep.

## sending

Sending defaults copied into new accounts.

- `sending.daily_allowance` (default `200`, 1–100000): Maximum messages sent per account per local day.
- `sending.window_start` (default `0`, 0–23): First local hour when sending is allowed, inclusive.
- `sending.window_end` (default `24`, 1–24): Last local hour when sending is allowed, exclusive. Must differ from `window_start`.
- `sending.jitter_min` (default `30`, 0–3600): Minimum seconds between sends on one account.
- `sending.jitter_max` (default `90`, 0–3600): Maximum seconds between sends on one account. Must be at least `jitter_min`.
- `sending.max_in_flight` (default `2`, 1–64): Maximum concurrent sends per account.
- `sending.enabled` (default `true`): Whether automatic sending is enabled.
- `sending.enforcement_mode` (default `permissive`, `permissive|strict`): `permissive` lets account overrides win; `strict` uses the global values.
- `sending.timezone` (default `UTC`): IANA name or UTC offset like `+1` or `-3` used for the send day.

## dispatch

Dispatcher loop, retry, and concurrency settings.

- `dispatch.tick_s` (default `2.0`, 0.05–60): Seconds between dispatcher cycles.
- `dispatch.max_attempts` (default `5`, 1–20): Maximum send attempts before a job is failed.
- `dispatch.retry_base_s` (default `30`, 1–3600): Base delay in seconds for retry backoff.
- `dispatch.retry_factor` (default `2.0`, 1.0–10.0): Multiplier applied to the retry delay.
- `dispatch.retry_cap_s` (default `3600`, 1–86400): Maximum retry delay in seconds (must be at least `retry_base_s`).
- `dispatch.retry_jitter` (default `0.2`, 0.0–1.0): Fraction of retry delay applied as random spread.
- `dispatch.global_in_flight` (default `8`, 1–256): Maximum concurrent sends across all accounts.
- `dispatch.parallel_sends` (default `false`): Allow more than one send in flight. Off by default; one send at a time is the recommended and safest mode.
- `dispatch.api_max_concurrency` (default `1`, 1–16): Maximum parallel Gmail API sends when `parallel_sends` is on. Ignored while `parallel_sends` is off.
- `dispatch.smtp_seats` (default `1`, 1–10): Distinct SMTP mailboxes in the serial send rotation. This is **not** parallel sending. Values above 3 are risky and strongly warned; setting high values can trigger confirmations/warnings in the CLI.
- `dispatch.smtp_seat_sticky` (default `true`): Hold an SMTP seat until a cap, a real transport failure, or batch drain when `smtp_seat_after_batch` is enabled. Read-only commands, such as capacity, ETA, and show views, never rotate a seat. If the holder has no work in a cycle, OAuth accounts use their API bindings and the seat stays put. Only a working account with no API path may borrow the seat for that cycle; the holder is not changed.
- `dispatch.smtp_seat_max_s` (default `0`, 0–86400): Seconds before a sticky seat rotates; `0` disables the cap.
- `dispatch.smtp_seat_max_sends` (default `0`, 0–1000000): Successful SMTP sends before a sticky seat rotates; `0` disables the cap. Planning calls do not count as sends.
- `dispatch.smtp_seat_after_batch` (default `false`): When true, rotate the sticky seat after the batch that first held it has no queued, sending, `retry_wait`, or awaiting-approval jobs. When false, batch drain does not release the seat.
- `dispatch.network_cooldown_after` (default `2`, 1–20): Consecutive network failures before a binding cools down.
- `dispatch.network_cooldown_s` (default `60`, 1–86400): Base cool-down in seconds after a network failure.
- `dispatch.quota_cooldown_s` (default `300`, 1–86400): Cool-down in seconds when a provider reports quota limits.
- `dispatch.capacity_advice` (default `true`): Warn when a selection runs on a single sequential seat.
- `dispatch.capacity_warn_messages` (default `10`, 1–100000): Message count at which capacity advice becomes a warning.
- `dispatch.capacity_warn_on_window` (default `true`): Escalate when an estimate spills past the send window.
- `dispatch.eta_horizon_days` (default `30`, 1–365): Days the finish estimate may walk before reporting `beyond_horizon`.
- `dispatch.eta_refresh_s` (default `30.0`, 0.5–3600): Minimum seconds between interactive ETA recomputations.
- `dispatch.pause_max_s` (default `2592000`, 1–31536000): Maximum duration accepted by service pause `--for`.
- `dispatch.pause_reason_max` (default `200`, 1–2000): Maximum characters stored in a pause reason.
- `dispatch.seat_hole_warn` (default `true`): Warn when a pause drops throughput or holds pinned work.
- `dispatch.shutdown_join_s` (default `5.0`, >0, ≤30): Seconds to wait for a dispatcher cycle to stop.

## followups

Follow-up planning settings.

- `followups.check_s` (default `30.0`, 0.05–3600): Seconds between follow-up planning cycles.
- `followups.sync_timeout_s` (default `30.0`, >0, ≤300): Seconds to wait for a mailbox sync before planning.
- `followups.defer_s` (default `300.0`, 1–86400): Seconds to defer a follow-up when its parent is not ready.

## retention

Retention and pruning settings.

- `retention.check_s` (default `3600.0`, 0.05–86400): Seconds between retention passes.
- `retention.jobs_days` (default `30`, 1–3650): Days to keep finished jobs.
- `retention.jobs_max` (default `10000`, 1–1000000): Maximum finished jobs to keep.
- `retention.mail_days` (default `90`, 1–3650): Days to keep inbound messages.
- `retention.hourly_days` (default `90`, 1–3650): Days to keep hourly activity rows.
- `retention.daily_days` (default `730`, 1–3650): Days to keep daily activity rows.

## events

Event ring and stream settings.

- `events.ring_size` (default `10000`, 1–1000000, restart required): Number of recent events kept for replay.
- `events.queue_size` (default `1000`, 16–100000, restart required): Maximum queued events per stream subscriber.
- `events.keepalive_s` (default `15.0`, >0, ≤300): Seconds between SSE keepalive frames.

## vault

Vault key derivation and throttle settings.

- `vault.kdf_memory_kib` (default `65536`, 8192–1048576): Argon2id memory in KiB when a vault is created.
- `vault.kdf_iterations` (default `3`, 1–10): Argon2id iterations when a vault is created.
- `vault.kdf_lanes` (default `1`, 1–8): Argon2id lanes when a vault is created.
- `vault.kdf_target_ms` (default `250`, 50–2000): Target derivation time in milliseconds.
- `vault.kdf_max_memory_kib` (default `262144`, 8192–1048576): Maximum Argon2id memory in KiB (must be at least `kdf_memory_kib`).
- `vault.free_attempts` (default `5`, 0–100): Failed unlocks allowed before throttling starts.
- `vault.base_delay_s` (default `1.0`, >0, ≤60): Base throttle delay in seconds after failed unlocks.
- `vault.max_delay_s` (default `300.0`, 1–3600): Maximum throttle delay in seconds (must be at least `base_delay_s`).

## connect

OAuth and IMAP connection settings.

- `connect.oauth_attempt_ttl_s` (default `600`, 5–3600): Seconds an OAuth attempt stays valid.
- `connect.oauth_timeout_s` (default `15.0`, >0, ≤120): Seconds to wait for OAuth network calls.
- `connect.imap_timeout_s` (default `15.0`, >0, ≤120): Seconds to wait for IMAP network calls.
- `connect.token_refresh_margin_s` (default `120`, 0–3600): Seconds before expiry to refresh an access token.
- `connect.shutdown_join_s` (default `2.0`, >0, ≤30): Seconds to wait for OAuth flows to stop.
- `connect.auth_check_concurrency` (default `4`, 1–16): Accounts checked in parallel after vault unlock.

## inbound

Inbound watcher and ingest settings.

- `inbound.source` (default `auto`, `auto|imap|gmail_api`): Default inbound owner. `auto` keeps IMAP for every auth kind and uses the Gmail API only as the completeness sweep.
- `inbound.ingest_since_init` (default `true`): Only ingest messages dated on or after this installation was first initialized. Turn this off to backfill older mail up to the configured initial-sync window.
- `inbound.api_poll_s` (default `60.0`, 10–300): Seconds between Gmail API history polls when it owns an account.
- `inbound.sweep_tick_s` (default `60.0`, 10–3600): Base gap between fleet sweep slots (not a per-account interval).
- `inbound.sweep_slot_jitter` (default `0.25`, 0–0.5): Fraction of `sweep_tick_s` added randomly to each slot.
- `inbound.sweep_accounts_per_tick` (default `1`, 1–5): Accounts swept sequentially in one slot.
- `inbound.sweep_initial_days` (default `7`, 0–3650): Backfill window on the first Gmail API sync or sweep.
- `inbound.sweep_limit` (default `500`, 1–5000): Messages fetched per Gmail API sweep or backfill.
- `inbound.idle_fleet_cap` (default `20`, 1–100): Accounts allowed to hold an IMAP IDLE connection.
- `inbound.idle_heartbeat_s` (default `60.0`, 30–1740): Maximum IDLE silence before a NOOP liveness check.
- `inbound.idle_timeout_s` (default `1500.0`, 10–1740): Seconds an IMAP IDLE connection waits before reconnecting.
- `inbound.poll_interval_s` (default `300.0`, 5–3600): Seconds between polls when IDLE is unavailable.
- `inbound.initial_sync_days` (default `7`, 0–3650): Days of mail to fetch on the first sync.
- `inbound.initial_sync_limit` (default `500`, 1–100000): Maximum messages to fetch on the first sync.
- `inbound.body_max_bytes` (default `2097152`, 1024–268435456): Maximum body bytes stored per inbound message.
- `inbound.fetch_batch` (default `25`, 1–500): Messages fetched per IMAP batch.
- `inbound.ingest_timeout_s` (default `60.0`, >0, ≤600): Seconds to wait for inbound ingestion.
- `inbound.backoff_s` (default `[5, 15, 60, 300, 900]`, 1–16 positive ascending values): Retry delays in seconds for inbound failures.
- `inbound.shutdown_join_s` (default `2.0`, >0, ≤30): Seconds to wait for watcher threads to stop.

## outbound

Outbound send and reconciliation settings.

- `outbound.smtp_timeout_s` (default `30.0`, >0, ≤300): Seconds to wait for SMTP network calls.
- `outbound.api_timeout_s` (default `60.0`, >0, ≤300): Seconds to wait for Gmail API requests.
- `outbound.lease_seconds` (default `120`, 10–3600): Seconds a job lease is held while sending.
- `outbound.reconcile_attempts` (default `3`, 1–10): Sent-folder searches after an uncertain send.
- `outbound.reconcile_delay_s` (default `1.0`, 0–60): Seconds between Sent-folder searches.
- `outbound.keepalive` (default `true`): Keep SMTP sessions open and reuse them for later sends.
- `outbound.keepalive_idle_s` (default `300`, 5–3600): Seconds an idle SMTP session is kept before it is closed.
- `outbound.keepalive_max_sessions` (default `1`, 1–16): SMTP sessions kept open per binding.
- `outbound.keepalive_noop_s` (default `60`, 1–3600): Seconds before a reused session is checked with NOOP.

## intake

Campaign input and attachment limits.

- `intake.max_messages` (default `10000`, 1–1000000): Maximum messages in one campaign.
- `intake.max_body_bytes` (default `1000000`, 1024–26214400): Maximum body bytes per campaign message.
- `intake.max_attachment_bytes` (default `26214400`, 1024–104857600): Maximum bytes per campaign attachment.
- `intake.max_file_bytes` (default `67108864`, 1024–536870912): Maximum input file size in bytes.
- `intake.sample_count` (default `5`, 1–20): Number of sample recipients in a review batch.

## config

Configuration reload settings.

- `config.reload_check_s` (default `0.5`, 0.05–60): Seconds between checks of `config.toml` for hand edits.

## cli

Command line client behavior.

- `cli.timeout_s` (default `10.0`, >0, ≤60): Seconds a CLI request waits for the daemon.
- `cli.page_lines` (default `40`, 0–10000): Lines before interactive output is paged; `0` disables paging.
- `cli.glyphs` (default `auto`, `auto|nerd|ascii`): Glyph set.
- `cli.tables` (default `true`): Always draw boxed tables. Set false to fall back to stacked fields when the terminal is too narrow for the grid.
- `cli.list_order` (default `newest_first`, `newest_first|oldest_first`): Default row order for `batch list`, `job list`, `failed list`, `mail list`, and `mail threads`. `--newest-first` and `--oldest-first` override it.
- `cli.update_check` (default `true`): Check GitHub for a newer release on CLI commands and show an update-available footer. Set false to disable the check entirely.
- `cli.update_check_interval_s` (default `86400`, 60–604800): Minimum seconds between GitHub update checks. The result is cached in the state directory and checked at most once per interval.

## connectivity

Internet reachability watchdog.

- `connectivity.enabled` (default `true`): Watch for internet outages and pause network work while offline.
- `connectivity.probe_host` (default `1.1.1.1`): Host for the TCP reachability probe.
- `connectivity.probe_port` (default `443`, 1–65535): Port for the TCP reachability probe.
- `connectivity.interval_s` (default `15.0`, >0, ≤3600): Seconds between reachability probes.
- `connectivity.jitter_s` (default `5.0`, 0–3600): Maximum extra random delay added to each probe interval.
- `connectivity.timeout_s` (default `3.0`, >0, ≤60): Seconds a single probe waits before it counts as failed.
- `connectivity.confirm_failures` (default `3`, 1–20): Consecutive failed probes needed to call the internet down.
- `connectivity.confirm_successes` (default `3`, 1–20): Consecutive successful probes needed to resume after an outage.

## backfill

Gmail provider thread id backfill worker settings. This worker fills missing
thread ids on older Gmail messages so threads can be grouped correctly.

- `backfill.enabled` (default `true`): Whether the Gmail provider thread id backfill worker runs.
- `backfill.page_size` (default `50`, 1–10000): Holes pulled from the database per drain turn.
- `backfill.max_accounts` (default `1`, 1–64): Accounts drained in parallel lanes.
- `backfill.max_concurrency` (default `2`, 1–16): In-flight lookups within one account.
- `backfill.jitter_s` (default `2.0`, 0–3600): Minimum seconds between API or IMAP calls on one lane.
- `backfill.jitter_max_s` (default `5.0`, 0–3600): Upper bound of the call jitter. Must be at least `jitter_s`.
- `backfill.retry_after_days` (default `7`, 0–365): Days of repeated lookup errors before a hole is marked unresolved. Confirmed absence is decided by `settle_s` instead.
- `backfill.settle_s` (default `900.0`, 0–2678400): Seconds after the send before a full-scope miss is treated as absence. Covers Gmail search indexing, not a multi-day wait.
- `backfill.retry_base_s` (default `60.0`, 0–86400): First delay before retrying an ambiguous or failed lookup.
- `backfill.retry_max_s` (default `21600.0`, 0–604800): Upper bound of the exponential lookup retry delay. Must be at least `retry_base_s`.
- `backfill.recheck_s` (default `3600.0`, 0.05–86400): Idle-mode hole re-check interval.
- `backfill.imap_chunk` (default `500`, 1–10000): UIDs per IMAP FETCH chunk in the bulk sweep.
- `backfill.imap_min_holes` (default `5`, 1–100000): Below this hole count, skip the IMAP sweep and use the API lookups.
- `backfill.startup_delay_s` (default `30.0`, 0–3600): Daemon-start stagger before the first hole count.
- `backfill.pass_cooldown_s` (default `300.0`, 0–86400): Wait after a drain turn that filled no holes.

## See also

- [../part-ii/17-config/config.md](../part-ii/17-config/config.md) — view and set configuration from the CLI
- [../part-ii/01-service/service.md](../part-ii/01-service/service.md) — restart the daemon for restart-required changes
- [../part-ii/11-sending/sending.md](../part-ii/11-sending/sending.md) — sending policy and overrides
- [34-safety.md](34-safety.md) — safety-related behavior

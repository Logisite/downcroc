---
title: config
commands: [config, config.show, config.schema, config.set]
flags: []
concepts: []
screens: []
---

# config

`config` lets you view and change downcroc’s configuration. You can see the effective configuration, inspect the schema of supported fields, and set individual fields by dotted path.

## Usage

```text
downcroc config <action> [key] [value]
```

Actions: `show`, `schema`, `set`. If no action is given in an interactive session, a config menu may be offered; otherwise `show` is displayed.

## Actions

### show

Shows the effective configuration.

```text
downcroc config show
```

- Displays the configuration file path and the effective config values. If the config could not be read cleanly, an error/reason is shown.
- Each field is shown with its value and whether it comes from the config file or is a default.

**Output**

- Default: prints the config path (and any read error) and a table of fields, values, and source (`file` or `default`).
- With `--json`: prints the config payload as JSON (including path, config, and document/source information as available).

### schema

Shows every supported configuration field.

```text
downcroc config schema
```

- Lists all supported fields with their dotted path, type, default, allowed values or range (when applicable), and description.

**Output**

- Default: a table of field, type, default, range/values, and description.
- With `--json`: the schema (fields and their metadata) as JSON.

Use `schema` to discover valid field names, types, defaults, and whether a change requires a restart. `downcroc config schema` lists every supported field (and `downcroc config show` shows the effective values and their source). For a written reference of all `config.toml` fields and defaults, see [Part III: Configuration reference](../part-iii/38-config.md).

### set

Sets one configuration field.

```text
downcroc config set [key] [value]
```

- `key` is a dotted path, for example `sending.jitter_min`. `value` is a JSON literal or plain text; if omitted in an interactive session you are prompted for the value (showing the current value as the default).
- The value is parsed according to the field type when known (strings can be passed as plain text; other types accept JSON literals or plain text where appropriate) and applied as a patch to that field.

**Behavior and safety**

- If the value is unchanged, the command reports that nothing changed.
- Some fields require a daemon restart to take effect. When such a field is changed, the command tells you to restart: `downcroc service restart`.
- **SMTP seats (`dispatch.smtp_seats`)** have extra warnings and confirmation: values above 1 warn that SMTP seats rotate serially across distinct mailboxes (not parallel sending and not added capacity). Values above 3 are treated as critical-risk (each extra mailbox can be throttled or suspended by Gmail and rotation is still serial). In an interactive, non-JSON session, setting seats above 3 requires typing the value to confirm.

**Output**

- Default: reports the change (old → new) or that the field is unchanged, and prints restart/risk warnings when applicable.
- With `--json`: prints `key`, `old`, `new`, `changed`, `restart_required`, and `risk` (for seat risk, when applicable).

If invoked as `config set` without a key in an interactive session, a config-set menu may be offered; otherwise a usage error is raised.

## Common flags

`--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc config show` — show effective configuration.
- `downcroc config schema` — list supported fields, types, and defaults.
- `downcroc config set sending.jitter_min 20` — set a field.
- `downcroc config set dispatch.smtp_seats 2` — set SMTP seats (with rotation warning as applicable).

## See also

- [../part-iii/38-config.md](../part-iii/38-config.md) — full configuration field reference
- [../01-service/service.md](../01-service/service.md) — restart the daemon to apply restart-required changes
- [../11-sending/sending.md](../11-sending/sending.md) — sending policy and overrides
- [../02-status/status.md](../02-status/status.md) — view current system status
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose configuration/installation issues
- [../part-i/01-starting/set-the-rules.md](../part-i/01-starting/set-the-rules.md) — setting rules for sending

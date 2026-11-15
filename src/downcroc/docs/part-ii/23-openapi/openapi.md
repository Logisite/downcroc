---
title: openapi
commands: [openapi]
flags: [--mkdir]
concepts: []
screens: []
---

# openapi

`openapi` exports downcroc’s HTTP API specification as an OpenAPI document (JSON). This is useful for generating clients, inspecting available endpoints, or integrating with tooling that consumes OpenAPI.

## Usage

```text
downcroc openapi [--output FILE] [--mkdir]
```

- `--output FILE` writes the document to a file (or to stdout when omitted or set to `-`). `--output`/`-o` specifies the destination.
- `--mkdir` creates the parent directory of the output file if it does not exist.

## Behavior

- Builds the OpenAPI document from the application’s API definition.
- Writes the JSON (pretty-printed) to stdout, or to the given file path. When writing to a file it reports the path written. If the output path is a directory, the command fails; if the parent directory does not exist, it fails unless `--mkdir` is provided (in which case the parent directory is created).
- The export is recorded in logs with the destination and route count.

## Common flags

`openapi` supports the command’s own `--output`/`-o` and `--mkdir` options. (As with other commands, run with `--help` to see the exact flags in your version.)

## Examples

- `downcroc openapi` — print the OpenAPI document to stdout.
- `downcroc openapi -o openapi.json` — write the document to `openapi.json`.
- `downcroc openapi -o build/api/openapi.json --mkdir` — write to a path, creating parent directories.

## See also

- [../22-docs-help/docs-help.md](../22-docs-help/docs-help.md) — read the documentation book and command help
- [../02-status/status.md](../02-status/status.md) — daemon and API availability
- [../19-logs/logs.md](../19-logs/logs.md) — daemon log (export is logged)

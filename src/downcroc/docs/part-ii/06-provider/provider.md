---
title: provider
commands: [provider]
flags: [provider.add --api-base-url, provider.edit --api-base-url, provider.add --api-max-concurrency, provider.edit --api-max-concurrency, provider.add --api-rate-per-min, provider.edit --api-rate-per-min, provider.add --auth-kind, provider.edit --auth-kind, provider.credentials.set --client, provider.credentials.remove --force, provider.add --imap-host, provider.edit --imap-host, provider.add --imap-port, provider.edit --imap-port, provider.add --imap-tls, provider.edit --imap-tls, provider.add --label, provider.credentials.set --label, provider.edit --label, provider.add --notes, provider.edit --notes, provider.add --oauth-client-id, provider.edit --oauth-client-id, provider.add --oauth-tenant, provider.edit --oauth-tenant, provider.add --password-file, provider.edit --password-file, provider.add --sent-folder, provider.edit --sent-folder, provider.add --smtp-host, provider.edit --smtp-host, provider.add --smtp-port, provider.edit --smtp-port, provider.add --smtp-tls, provider.edit --smtp-tls, provider.add --transport, provider.edit --transport]
concepts: []
screens: []
---

# provider

`provider` inspects and manages [[provider]] declarations and imported OAuth client credentials.

A **provider declaration** is the description of how downcroc connects to and uses a mail provider: which IMAP and SMTP servers, ports, and encryption to use, how accounts authenticate, which folder holds sent mail, which send transport to use (for example SMTP or the Gmail API), and any related API settings. A declaration can be ready to use or it can be missing required information; `provider` lets you see that state and fill in what is needed.

**Provider credentials** (OAuth clients) are imported OAuth client records (for example a Google OAuth desktop client JSON). They hold the client information accounts use when they sign in with OAuth.

## Usage

```text
downcroc provider <action> [options]
```

Top-level actions: `list`, `show`, `add`, `edit`, `remove`, `credentials`.

In interactive mode, running `provider` without an action can open the provider menu so you can choose what to do.

## Provider declarations

### list

Lists all providers and their readiness.

**What it shows**

For each provider: its id, label, auth kind (the authentication “door”, such as OAuth or app password), IMAP host and port, SMTP host and port, whether it is ready, and either a note or the list of missing requirements. If a provider is ready and has notes, the notes are shown as well.

**Output**

- Default: a human-readable list.
- `--json`: the provider list as machine-readable JSON.

Use `list` to see which providers are configured, which ones are ready to use, and, for those that are not ready, exactly what still needs to be set.

### show

Shows the full declaration for one provider.

```text
downcroc provider show [provider_id]
```

- If `provider_id` is omitted in interactive mode, you can choose a provider from the available ones.
- **What it reports:** id, label, auth kind, readiness, and source (where the declaration comes from, or “built in”). It also reports IMAP host, port, and TLS mode; SMTP host, port, and TLS mode; the sent folder; the attachment size limit; and the transport. When the transport is `gmail_api`, it additionally reports the API base URL, API max concurrency, and API rate per minute.
- If the provider is not ready, `show` lists the missing requirements so you know what to fix. If there are notes, they are shown.
- With `--json`, prints the provider as machine-readable JSON.

### add

Creates or writes a provider declaration.

```text
downcroc provider add [provider_id] [options]
```

**Identifying the provider**

- `provider_id` is the identifier for the declaration. If you omit it in interactive mode, you are prompted for it.

**Supplying fields**

- You can supply declaration fields as command-line options (see [Provider declaration options](#provider-declaration-options)).
- If you do not provide field values, `add` collects them interactively when running in an interactive session: it asks for the label, IMAP host/port/TLS, SMTP host/port/TLS, authentication kind, and sent folder.
- In non-interactive mode, required values must be provided via flags; if they are missing, the command fails asking for the necessary input rather than prompting.

**OAuth-specific details**

- For OAuth authentication (`--auth-kind oauth2`), the provider may need an OAuth client id and, for Microsoft providers, a tenant. You can set these with `--oauth-client-id` and `--oauth-tenant`.
- The OAuth client secret can be provided via `--password-file PATH` (read from a protected file). In interactive flows you may be prompted for OAuth details and, when appropriate, for a client secret.

**On success**

- The declaration is written and its readiness is reported. If required settings are still missing, the command reports what is missing and suggests editing the provider with `downcroc provider edit <id>`.

### edit

Changes an existing provider declaration.

```text
downcroc provider edit [provider_id] [options]
```

**Identifying the provider**

- If `provider_id` is omitted in interactive mode, you can choose which provider to edit.

**How changes are applied**

- If you pass one or more declaration options, only those supplied fields are updated. The OAuth client secret can be updated via `--password-file PATH` when relevant.
- If you pass no options in interactive mode, `edit` lets you select which fields to change from the current declaration and prompts you for their new values, so you do not have to re-enter everything.
- In non-interactive mode, at least one field/option must be provided; you cannot interactively pick fields without a terminal.

**On success**

- After updating, `edit` reports the provider’s readiness (and lists missing requirements, if any). When not running with `--quiet`, it also reports where the declaration was written.
- With `--json`, prints the updated provider.

### remove

Removes a provider declaration.

```text
downcroc provider remove [provider_id] [--yes]
```

- If `provider_id` is omitted in interactive mode, you can choose a provider.
- Deletion requires confirmation. Pass `--yes` to skip the confirmation prompt. In non-interactive use, confirmation must be satisfied appropriately; if you decline (or cannot confirm), the operation is cancelled.
- With `--json`, prints the removal result.

## Provider declaration options

These options apply to `add` and to `edit` (to set or change the corresponding field).

`--label LABEL`
: The name shown for the provider in lists.

`--imap-host IMAP_HOST`
: IMAP server host name.

`--imap-port IMAP_PORT`
: IMAP server port (commonly 993).

`--imap-tls {ssl|starttls|none}`
: IMAP encryption/TLS mode.

`--smtp-host SMTP_HOST`
: SMTP server host name.

`--smtp-port SMTP_PORT`
: SMTP server port (commonly 587).

`--smtp-tls {starttls|ssl|none}`
: SMTP encryption/TLS mode.

`--auth-kind {oauth2|app_password|none}`
: The authentication method. `oauth2` means accounts sign in with an OAuth client, `app_password` means they use an app password, and `none` means no authentication of that kind applies.

`--sent-folder SENT_FOLDER`
: The folder that holds sent mail for this provider.

`--notes NOTES`
: A note shown in provider listings (for example a reminder about provider-specific setup).

`--oauth-client-id OAUTH_CLIENT_ID`
: OAuth application client id, used with OAuth providers.

`--oauth-tenant OAUTH_TENANT`
: OAuth tenant identifier, used for Microsoft providers.

`--transport {smtp|gmail_api}`
: The send mechanism the provider supports. `smtp` sends over SMTP; `gmail_api` sends via the Gmail API. API-related settings below apply to API transports.

`--api-base-url API_BASE_URL`
: REST API base URL for API transports.

`--api-max-concurrency API_MAX_CONCURRENCY`
: Maximum number of concurrent REST requests for the API transport.

`--api-rate-per-min API_RATE_PER_MIN`
: Maximum REST requests per minute for the API transport.

`--password-file PATH`
: Read the OAuth client secret from a protected file at `PATH` (for example mode 0600). Used when configuring OAuth (`oauth2`) providers.

## OAuth client credentials

```text
downcroc provider credentials <action> [options]
```

These commands import and inspect OAuth client credentials used for OAuth sign-in — for example, importing a Google OAuth desktop client JSON so accounts on a Gmail provider can authorize.

### credentials set

Imports an OAuth client.

```text
downcroc provider credentials set [provider_id] [--client PATH] [--label LABEL]
```

- Imports the client JSON. `--client PATH` specifies the path to the client JSON file to import.
- In interactive mode, if `--client` is not provided, you are prompted for the client JSON path. The prompt can guide you to download the Desktop OAuth client JSON from Google Cloud (APIs and Services → Credentials → your OAuth client → Download JSON).
- In non-interactive mode, the client path/information must be provided. If the client is not configured, the command fails with a hint to run `downcroc provider credentials set ... --client PATH`.
- `--label LABEL` can give the imported client a name.

### credentials list

Lists imported OAuth clients.

```text
downcroc provider credentials list [provider_id]
```

- Lists imported clients. When `provider_id` is given, the listing can be scoped to that provider where applicable.
- With `--json`, prints the list as machine-readable JSON.

### credentials show

Shows one imported OAuth client.

```text
downcroc provider credentials show [client_id]
```

- Displays details for the specified client.
- With `--json`, prints the client as machine-readable JSON.

### credentials remove

Deletes an imported OAuth client.

```text
downcroc provider credentials remove [client_id] [--force] [--yes]
```

- Deletion requires confirmation unless `--yes` is given.
- `--force` moves dependent bindings to re-authentication if needed. Use this when accounts or bindings depend on this client and must be moved to a state where they can be re-authenticated with a different client.
- With `--json`, prints the removal result.

## Common flags

Common flags: `--json`, `--no-input`, `--yes` (where confirmation applies), `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## Examples

- `downcroc provider list` — list all providers, their readiness, and any missing requirements.
- `downcroc provider show gmail` — show the full Gmail provider declaration.
- `downcroc provider add fastmail` — create a Fastmail provider declaration, prompting for details interactively if needed.
- `downcroc provider edit gmail --transport gmail_api` — update the Gmail declaration to use the Gmail API transport.
- `downcroc provider remove old-provider --yes` — remove a provider declaration without prompting.
- `downcroc provider credentials set gmail --client ~/Downloads/client_secret.json` — import a Google OAuth client JSON for Gmail.
- `downcroc provider credentials list` — list imported OAuth clients.
- `downcroc provider credentials remove client_123 --yes` — delete an imported OAuth client.

## See also

- [../07-account/account.md](../07-account/account.md) — add and connect accounts that use providers
- [../part-i/01-starting/gmail.md](../part-i/01-starting/gmail.md) — setting up Gmail and importing an OAuth client
- [../part-i/01-starting/connect-a-mailbox.md](../part-i/01-starting/connect-a-mailbox.md) — connecting a mailbox
- [../03-init/init.md](../03-init/init.md) — first-run setup, including provider and account steps
- [../16-doctor/doctor.md](../16-doctor/doctor.md) — diagnose provider and transport readiness

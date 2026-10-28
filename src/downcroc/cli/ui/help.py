from __future__ import annotations

import re

from downcroc.cli.ui.session import Ui

TOPICS: dict[str, str] = {
    "ui": """ui

  downcroc is a command line tool. Every flag is the complete script
  interface; prompts appear only when stdin and stdout are terminals.

  Global flags
    --json            machine-readable output, never prompts
    --no-input        fail instead of asking
    --yes             consent for a named destructive action
    --wide            use the full terminal width
    --full            never truncate record values
    --glyphs nerd     Nerd Font glyphs; ASCII unless cli.glyphs says nerd
    --color always    auto, always, or never
    --quiet           suppress next-step lines
    --timeout S       daemon request timeout
    --no-pager        never page long output

  Default glyphs
    downcroc config set cli.glyphs nerd

  Prompt keys
    enter accepts the shown default, q goes back, ctrl-c cancels.

  Related: send, accounts, review, troubleshooting
""",
    "vault": """vault

  The vault holds mailbox credentials. One master password protects it.
  The password cannot be recovered and is never stored in the config.

  Commands
    downcroc vault init                 create it, double prompt
    downcroc vault status               state, path, attempts left
    downcroc vault unlock               unlock; idempotent
    downcroc vault lock                 lock now
    downcroc vault lock --forget        lock and delete the stored password
    downcroc vault keyring status       on (secret service), off, unavailable
    downcroc vault keyring enable       store the master password
    downcroc vault keyring disable      delete it; the password is unchanged

  Scripts
    printf '%s\\n' "$PASS" | downcroc vault unlock --password-stdin
    downcroc vault unlock --password-file /run/secrets/downcroc

  The password file must be a regular 0600 file, not a symlink, and must
  contain exactly one line. Extra non-empty lines are rejected.

  The credential store holds only the master password, under the absolute
  vault path. The daemon never reads it. While it is enabled, anything
  running as you in your session can unlock the vault.

  Related: accounts, troubleshooting
""",
    "accounts": """accounts

  An account is one mailbox. Adding it creates a pending row; connecting
  it proves the IMAP login and stores the credential.

  Commands
    downcroc account list
    downcroc account add --provider gmail --address you@example.com
    downcroc account connect ACCOUNT_ID
    downcroc account attempt ACCOUNT_ID --wait
    downcroc account verify ACCOUNT_ID
    downcroc account watch ACCOUNT_ID --on
    downcroc account delete ACCOUNT_ID --yes

  Providers offer one or two doors:
    app password   about 2 minutes, no browser
    oauth client   about 10 minutes once, survives a password change

  A failed connect stores nothing and leaves the account pending, so the
  step can be resumed. The result names the IMAP host and sent folder; it
  never claims SMTP was checked.

  Related: providers, vault, send
""",
    "providers": """providers

  A provider declaration names the IMAP and SMTP hosts, ports, TLS mode,
  and auth kind. Declarations ship with downcroc; user files live at
  ~/.config/downcroc/providers.toml and providers.d/.

  Commands
    downcroc provider list
    downcroc provider show gmail
    downcroc provider add fastmail
    downcroc provider edit gmail
    downcroc provider remove fastmail

  provider add never writes a secret. Mailbox passwords go to the vault.
  An OAuth client secret is written to providers.toml mode 0600 because
  the daemon needs it at token exchange.

  A provider row is ready when the fields its door needs are present.
  Gmail's OAuth door needs both oauth_client_id and oauth_client_secret.

  Related: accounts, vault
""",
    "send": """send

  downcroc send validates a campaign, shows a preview, picks an account,
  and submits a batch.

  Commands
    downcroc send
    downcroc batch validate campaign.json
    downcroc batch submit campaign.json --approve none
    downcroc batch submit campaign.json --account acct_... --approve all
    downcroc batch submit campaign.json --dry-run

  Approval words
    none   hold everything for review
    one    send one sample now, hold the rest
    all    send as soon as each message is due

  --account pins every message to one account. It rewrites
  campaign.routing to fixed so the file and the flag cannot disagree.

  Related: batch, templates, review
""",
    "batch": """batch

  A campaign is either JSON or CSV plus a template. Detection is by
  content: a first byte of { or [ is JSON; anything else is CSV.

  JSON, one message
    [{"to": {"email": "ana@example.com"}, "subject": "Hello", "text": "Hi"}]

  JSON, object form
    {"schema": "downcroc.campaign/v1",
     "campaign": {"key": "march", "name": "March",
                  "routing": {"mode": "auto"},
                  "options": {"approval": "review"}},
     "messages": [], "followups": []}

  Duplicate addresses are an error unless options.allow_duplicates is true.
  A per-message account field is rejected: use campaign.routing.account.

  Discovery
    downcroc batch schema
    downcroc batch example --kind json
    downcroc batch validate campaign.json

  Related: send, templates
""",
    "templates": """templates

  A CSV campaign needs a template under ~/.config/downcroc/templates/.

  Layout
    templates/intro/template.toml
    templates/intro/body.txt
    templates/intro/body.html     optional
    templates/intro/assets/       optional

  template.toml
    subject = "Hello {{name}}"
    reply_to = "you@example.com"
    attachments = ["deck.pdf"]
    [defaults]
    name = "there"

  Commands
    downcroc template list
    downcroc template new intro
    downcroc template show intro
    downcroc template validate intro
    downcroc batch example --kind template --write .

  Variables are {{ name }}. Built-ins are email, batch_name, and date.
  Missing variables are errors naming the variable and the row.

  Related: batch, send
""",
    "review": """review

  A campaign submitted with approval review waits for a decision.

  Commands
    downcroc review
    downcroc batch list --state awaiting_approval
    downcroc batch show BATCH_ID
    downcroc batch approve BATCH_ID --mode one
    downcroc batch approve BATCH_ID --mode all
    downcroc batch cancel BATCH_ID --yes

  one sends exactly one sample and leaves the rest held. all releases the
  remaining messages. Cancelling does not recall mail already in flight.

  Related: send, batch
""",
    "service": """service

  The daemon is a local HTTP process bound to loopback. It starts locked.

  Commands
    downcroc serve                 foreground
    downcroc service start         detached, waits for health
    downcroc service restart       stop then start, data untouched
    downcroc service status        exit 1 unless running
    downcroc service install       register a login service
    downcroc service uninstall     data stays

  State and logs live under:
    $XDG_CONFIG_HOME/downcroc
    $XDG_DATA_HOME/downcroc
    $XDG_STATE_HOME/downcroc

  Related: vault, troubleshooting
""",
    "troubleshooting": """troubleshooting

  downcroc is not running
    downcroc service start
    downcroc service status

  The daemon does not answer
    downcroc status
    downcroc logs --level warning --since 15m
    raise the client wait with --timeout 30

  A mailbox will not connect
    downcroc provider show PROVIDER
    downcroc account show ACCOUNT
  Gmail app passwords are 16 letters with no spaces and need 2-Step
  Verification. An unpublished OAuth client issues seven-day refresh
  tokens; reconnect when the account becomes needs_reauth.

  A campaign will not validate
    downcroc batch validate FILE
    downcroc batch example --kind json
    downcroc batch schema

  The vault is throttled
    downcroc vault status
  Wait for retry_after_s, then unlock once. Stop retrying; a mailbox or
  the vault will lock you out.

  Related: ui, vault, accounts
""",
}

TOPICS["start"] = """start

  This is the first-run path. It takes about two minutes.

    downcroc init
    downcroc send

  init prints the three directories it owns, starts or installs the daemon,
  creates the vault, and adds one mailbox.

  The daemon runs on loopback only and starts locked. The vault password
  protects the mail credentials and cannot be recovered.

  Related: ui, vault, accounts
"""

TOPICS["glossary"] = """glossary

  signed in       a credential is stored and the IMAP login was proven
  needs re-auth   the stored credential was rejected; reconnect the account
  pending         the account exists but no credential was stored yet

  reply_state
    confirmed     an automatic reply was proven
    probable      a message looks like an automatic reply
    late          the reply arrived after the configured window
    bounced       a delivery failure

  queue states
    queued        waiting for its turn
    sending       in flight
    sent          accepted by the SMTP server
    retry_wait    a transient failure; it will be tried again
    failed        it will not be retried

  vault
    locked        encrypted, the password was not supplied yet
    throttled     too many unlock attempts; wait for retry_after_s

  Related: troubleshooting, mail, batch
"""

ALIASES = {"home": "ui", "help": "ui", "errors": "troubleshooting"}


def names() -> list[str]:
    return sorted(TOPICS)


def lookup(topic: str) -> str | None:
    key = topic.strip().casefold()
    key = ALIASES.get(key, key)
    return TOPICS.get(key)


def render(topic: str, ui: Ui | None = None) -> str | None:
    text = lookup(topic)
    if text is None:
        return None
    if ui is None:
        return text.rstrip() + "\n"
    return "\n".join(_style(text, ui)).rstrip() + "\n"


def summary(name: str) -> str:
    lines = [line.strip() for line in TOPICS[name].splitlines()[1:] if line.strip()]
    return lines[0] if lines else ""


def index(ui: Ui | None = None) -> str:
    if ui is None:
        lines = ["topics:", ""]
        for name in names():
            lines.append(f"  {name:<16} {summary(name)}")
        lines.append("")
        lines.append("run: downcroc help TOPIC")
        return "\n".join(lines) + "\n"
    lines = [ui.heading("Help topics"), ""]
    room = max(24, ui.width - 26)
    for name in names():
        text = summary(name)
        if len(text) > room:
            text = text[: room - 1] + "~"
        lines.append(f"  {ui.accent(ui.glyph('dot'))} {ui.bold(f'{name:<16}')} {text}")
    lines.append("")
    lines.append(f"  {ui.dim('run')} {ui.accent('downcroc help TOPIC')}")
    return "\n".join(lines) + "\n"


def _style(text: str, ui: Ui) -> list[str]:
    raw = text.rstrip().splitlines()
    title = raw[0].strip()
    out = [f"{ui.accent(ui.glyph('pointer'))} {ui.bold(title)}", ""]
    index = 1
    while index < len(raw):
        line = raw[index].rstrip()
        if not line.strip():
            if out[-1] != "":
                out.append("")
            index += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent >= 4:
            index = _group(raw, index, ui, out)
            continue
        _section(line.strip(), _next(raw, index), ui, out)
        index += 1
    return out


def _next(raw: list[str], index: int) -> str:
    spot = index + 1
    while spot < len(raw) and not raw[spot].strip():
        spot += 1
    return raw[spot] if spot < len(raw) else ""


def _section(text: str, following: str, ui: Ui, out: list[str]) -> None:
    if text.lower().startswith("related:"):
        names = text.split(":", 1)[1].strip()
        out.append(f"  {ui.dim('related')}  {_names(names, ui)}")
        return
    indent = len(following) - len(following.lstrip())
    heading = (
        len(text) <= 40 and not text.endswith((".", ":", "!", "?")) and indent >= 4
    )
    if heading:
        if out[-1] != "":
            out.append("")
        out.append(f"  {ui.bold(ui.accent(text))}")
        return
    out.append(f"  {text}")


def _names(text: str, ui: Ui) -> str:
    parts = [part.strip() for part in text.split(",")]
    return ui.dim(", ").join(ui.accent(part) for part in parts if part)


def _group(raw: list[str], start: int, ui: Ui, out: list[str]) -> int:
    end = start
    while end < len(raw) and raw[end].strip():
        end += 1
    block = [line.rstrip() for line in raw[start:end]]
    if _is_code(block):
        out.extend(f"  {ui.dim(line.strip())}" for line in block)
        return end
    for line in block:
        out.append(_bullet(line.strip(), ui))
    return end


def _is_code(block: list[str]) -> bool:
    first = block[0].strip()
    if first.startswith(("{", "[")):
        return True
    if first.startswith("templates/") and len(block) > 1:
        return True
    return any(" = " in line for line in block)


COMMANDS = ("downcroc ", "$", "printf ", "raise ")


def _bullet(text: str, ui: Ui) -> str:
    parts = re.split(r"\s{2,}", text, maxsplit=1)
    label = parts[0]
    detail = parts[1] if len(parts) > 1 else ""
    if detail:
        return f"  {ui.accent(ui.glyph('dot'))} {ui.accent(label)}  {detail}"
    if label.startswith(COMMANDS):
        return f"  {ui.accent(ui.glyph('choice'))} {ui.accent(label)}"
    return f"  {ui.dim(ui.glyph('dot'))} {label}"

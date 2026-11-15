---
title: sending
commands: [sending]
flags: [sending.set --daily-allowance, sending.set --for, sending.set --jitter-max, sending.set --jitter-min, sending.set --max-in-flight, sending.set --on, sending.set --window-end, sending.set --window-start]
concepts: [allowance, sending_window, jitter, max_in_flight]
screens: []
---

# sending

`sending` inspects and overrides the global send policy — the service-wide rules for how much and when mailboxes may send, and whether automatic sending is enabled.

The global policy is one layer in how downcroc decides when a message can go out. Per-account policy (`downcroc account policy`) can refine it for a specific mailbox. Limits set on a batch can only tighten (slow down) the effective result; a batch cannot make sending faster or looser than the policy allows. And pausing sending at the service level (`downcroc service pause` / `downcroc service resume`) holds dispatch without changing any of these policy values. `sending` is about the policy values and their overrides; it is not the same as pausing the service.

## Usage

```text
downcroc sending <action> [options]
```

Actions: `show`, `set`, `clear`.

## Actions

### show

Shows the effective global send policy. This action only reads state; it never changes it.

**What it tells you**

- The resolved (effective) policy values for the global scope — the actual limits and on/off state that apply after considering defaults and overrides.
- The source of each value, so you can see where an effective value comes from (for example a base/global setting versus an override that replaced it).
- If a temporary service override is currently active, `show` also reports the temporary override values and when that override expires.

**Output**

- Default: a human-readable view of the effective policy, its sources, and any active temporary override with its expiry.
- `--json`: the policy in machine-readable form.

Use `show` to understand the current global sending limits, to confirm whether automatic sending is on, and to see whether a temporary override is in effect and when it will end.

### set

Sets a global (service) sending override.

```text
downcroc sending set [policy fields] [--on|--off] [--for DURATION]
```

**What you can change**

- You provide one or more policy fields to change (see [Policy fields](#policy-fields)). Only the fields you specify are updated in the override; any fields you do not specify are left unchanged in that override layer.
- You can also pass `--on` or `--off` to enable or disable automatic sending globally as part of the same override.

**Temporary vs persistent override**

- With `--for DURATION` (for example `30s`, `15m`, `2h`, `7d`) the override is temporary: it takes effect now and expires after the given duration. While it is active, the effective policy shows it as a temporary service override with an expiry time. When the duration elapses, the temporary override expires and the effective policy reverts accordingly.
- Without `--for`, the change is applied as a service override that remains in effect until you remove it with `downcroc sending clear`.

**Validation and results**

- If you call `set` without providing any policy fields to change, the command fails with a usage error telling you to pass a field (for example `--daily-allowance` or `--off`).
- After applying the change, `set` shows the resulting effective policy so you can confirm the resolved values and their sources.

`set` affects the global policy layer. It does not pause or resume the service-level sending hold, and it does not modify per-account overrides.

### clear

Removes the global sending override.

**Behavior**

- Clears the service-level sending override so the effective global policy falls back to its underlying values (the base/global behavior without that override).
- Shows the resulting effective policy after clearing.

Use `clear` when you want to remove a global override you set earlier — including a temporary one applied at the service level — and return to the underlying policy.

## Policy fields

These fields can be provided to `sending set`. Each controls one aspect of how mailboxes send. (The same fields exist on per-account policy via `downcroc account policy set`; global `sending` sets them at the service-wide layer.)

`--daily-allowance N`
: The maximum number of messages a mailbox may send per local day. This is a per-account daily cap: it limits each mailbox individually (not the total across all mailboxes). See [[allowance]].

`--window-start HOUR`
: The first local hour when sending is allowed, inclusive. Valid range 0–23. Together with `--window-end` this defines the [[sending_window]]: the span of local hours during which sending may occur.

`--window-end HOUR`
: The last local hour when sending is allowed, exclusive. Valid range 1–24. The window start and end must differ — a zero-length window is not allowed. Sending is permitted only within the window defined by start and end.

`--jitter-min SECONDS`
: The minimum gap, in seconds, that downcroc leaves between sends on one mailbox. Jitter spaces sends out over time rather than firing them back-to-back; see [[jitter]].

`--jitter-max SECONDS`
: The maximum gap, in seconds, between sends on one mailbox. The maximum must be at least the minimum; downcroc chooses a gap within this range for each send.

`--max-in-flight N`
: The maximum number of sends a mailbox may have in progress at the same time. Keeping this bounded limits concurrency per mailbox; see [[max_in_flight]].

`--on` / `--off`
: Enable or disable automatic sending globally. `--off` turns global automatic sending off (as a policy override), so work will not be dispatched automatically under this policy; `--on` turns it on. These flags can be combined with `--for` to make the change temporary — for example, disabling sending for a fixed duration and having it re-enable when the override expires.

`--for DURATION`
: Makes the override temporary for the specified duration, such as `30s`, `15m`, `2h`, or `7d`. When the duration elapses, the temporary override expires and the effective policy reverts accordingly. Without `--for`, the override persists until you run `downcroc sending clear`.

Common flags: `--json`, `--no-input`, `--wide`, `--full`, `--glyphs {auto,nerd,ascii}`, `--color {auto,always,never}`, `--quiet`, `--timeout TIMEOUT`, `--no-pager`.

## How this layer relates to other controls

Understanding where `sending` fits helps avoid mixing it up with other ways to stop or slow work:

- **Per-account policy (`downcroc account policy`).** Sets overrides for a specific mailbox. The effective policy for an account is resolved from global settings together with account-level overrides (including temporary account overrides where applicable). Use `account policy` when you want one mailbox to behave differently from the rest.
- **Batch limits.** Limits set on a batch can only tighten (slow down) the effective sending behavior; they do not relax it beyond what the policy allows. A batch cannot override the policy to send more or faster.
- **Service-level pause (`downcroc service pause` / `service resume`).** Holds or releases dispatch at the service level. A pause stops sending from being dispatched but does **not** change the policy values shown by `sending show`; policy and pause are different controls that answer different questions (“what are the limits?” vs “is dispatch currently held?”). `downcroc service status` and `downcroc status` show when sending is paused at the service level.

## Examples

- `downcroc sending show` — show the effective global send policy, its sources, and any active temporary override with its expiry.
- `downcroc sending set --daily-allowance 100` — set a global override so each mailbox may send up to 100 messages per local day.
- `downcroc sending set --off --for 1h` — disable automatic sending globally for one hour as a temporary override; after an hour it expires and the previous behavior resumes.
- `downcroc sending set --window-start 8 --window-end 18` — restrict sending to between 08:00 and 18:00 local time.
- `downcroc sending set --jitter-min 60 --jitter-max 180` — set the gap between sends on a mailbox to between 60 and 180 seconds.
- `downcroc sending set --on` — re-enable automatic sending globally (as a service override).
- `downcroc sending clear` — remove the global sending override and return to the underlying values.

## See also

- [../07-account/account.md](../07-account/account.md) — per-mailbox send policy (`account policy`)
- [../01-service/service.md](../01-service/service.md) — service-level pause and resume of sending
- [../part-i/04-mailboxes/tune-a-mailbox.md](../part-i/04-mailboxes/tune-a-mailbox.md) — tuning allowances, windows, and pacing for a mailbox
- [../part-i/03-keeping-it-running/stuck.md](../part-i/03-keeping-it-running/stuck.md) — when work is paused or not moving
- [../part-iii/30-pipeline.md](../part-iii/30-pipeline.md) — how sending is scheduled and dispatched
- [../part-iii/33-states.md](../part-iii/33-states.md) — states related to queued and held work

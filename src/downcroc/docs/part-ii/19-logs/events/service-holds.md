---
title: Service, holds, and dispatch state log events
commands: []
flags: []
concepts: []
screens: []
---

# Service, holds, and dispatch state log events

Events for service-level sending pause/resume, holds, dispatch capacity, and connectivity-driven pause/resume. Primary emitters: `src/downcroc/core/holds.py`, `src/downcroc/core/dispatch/service.py`, `src/downcroc/core/bootstrap/foundation.py`, `src/downcroc/core/inbound/service.py` (connectivity pause/resume of watcher vs dispatch are distinct).

## Service pause and resume

- `service.paused` (**info**, log; also published) — sending was paused at the service level. Emitted when a pause takes effect (and the state/parameters changed).
  - `reason`: why sending is paused (cleaned/truncated to the configured max).
  - `actor`: actor/source of the pause when emitted from the holds path (e.g. `api`).
  - `until`: expiry time for a timed pause (when applicable).

- `service.resumed` (**info**, log; also published) — the service-level sending hold was cleared or expired. Emitted on explicit resume, when an expired timed pause is noticed/cleared (dispatcher/startup paths), or similar resume transitions.
  - `reason`: for example `manual` on explicit resume, or `expired` when a timed pause elapsed.

## Dispatch holds and capacity

- `dispatch.hold` (**info**, log; also published) — the dispatcher entered a hold state (e.g. service-level pause observed).
  - `hold_level` / `level`: the hold scope (e.g. `service`).
  - `id`: scope identifier (`null`/absent for a service-level hold).

- `dispatch.release` (**info**, log; also published) — the dispatcher released a hold.
  - `hold_level` / `level`: the hold scope.
  - `id`: scope identifier (when applicable).
  - `released_jobs`: count of jobs released (as emitted; may be 0 at the point of logging).

- `dispatch.capacity` (**published event**) — dispatch capacity/lanes changed due to a pause/resume or account impact.
  - `trigger`: what caused the change (e.g. pause/resume).
  - `lanes_before`, `lanes_after`: lane counts before/after.
  - `absorbed_by`: accounts/lanes absorbing impact (as computed).
  - `held_pinned`: pinned jobs held as a result (as computed).

## Connectivity-driven dispatch/watcher state

- `dispatch.paused` (**info**, log; also published) — dispatch paused because connectivity is unavailable.
  - `reason`: e.g. `connectivity`.

- `dispatch.resumed` (**info**, log; also published) — dispatch resumed after connectivity returned.
  - `reason`: e.g. `connectivity`.

(Watcher-side connectivity pause/resume is logged as `watcher.paused` / `watcher.resumed`; see [inbound-watcher.md](inbound-watcher.md).)

## See also

- [../logs.md](../logs.md) — reading and understanding the log
- [../../01-service/service.md](../../01-service/service.md) — service control and service-level pause/resume
- [../../02-status/status.md](../../02-status/status.md) — sending/paused state in overall status
- [jobs-dispatch.md](jobs-dispatch.md) — dispatch cycle and job/batch events

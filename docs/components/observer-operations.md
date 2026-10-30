---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Spectator, host operations and delivery

The spectator shows actual owned target images, mechanical resources/custody and
separately labelled player claims. It owns no actor capability. The operator's
Pause is an independent permanent stop. [Architecture](../architecture.md) and
[current contract](../contracts/computer-control.md) own system/port guarantees.

## Internal responsibilities

| Part | Owns |
| --- | --- |
| [Server](../../harness/server.py) | Selected `127.0.0.1` host/origin checks, bounded JSON, passive status/source routes and independent Pause. |
| [Web viewer](../../web/) | Actual source presentation, mechanical versus player-claim labels, host/resource status and Pause feedback. |
| [Activity projection](../../harness/observer.py) | Disposable bounded host tail and read-only computer-record snapshot; explicit original links and coverage, no custody or second journal. |
| [Custodian](../../tools/campaign_run.py) | Frozen admission validation, exact native target, store/server lifetime and final cleanup/accounting receipt. |
| [Preparation](../../tools/prepare_game.py) | Project-local windowed options, normal mouse input, wrapper/userdir and shared exclusion before changes. |
| [Build](../../tools/build_computer.py) | Current mechanical SDL adapter/fixture plus source/output provenance; no gameplay claim. |

## Projection and failure semantics

`GET /api/status` is passive `computer-status/1`; `/api/source/ID` serves current
session PNGs with retained identity/digest verification. A failed spectator image
read reports unavailable without calling actor-side source-failure fencing;
canonical actor/capture/input integrity behavior is unchanged. Browser reads do
not select a player store or create observations.
`GET /api/activity` is the bounded `observer-activity/1` projection described in
the [contract](../contracts/computer-control.md#passive-spectator-projections).
It uses the existing driver's trace consumer and a separate read-only SQLite
snapshot, never the player executor or a model request. Projection gaps cannot
renew or revoke custody. Original host trace/accounting remains authoritative.
`POST /api/pause` accepts `{}` and bypasses actor/executor/DB waits. Its
`computer-pause/1` response identifies the actual receiving session and original
stop facts; the request works without prior status or an activity response. Authenticated
actor tools use `/api/tool`; source reads use `/api/player-source`. No CORS/public
exposure, semantic recovery controls or browser-issued actor handoff exists.

Report stop-requested separately from native-confirmed Pause. A stale image or
retained launch receipt is historical evidence, not current liveness. Player claims
are fallible, separately labelled data. Delivered events, process absence and host
completion do not certify a save or objective. Unknown input remains stopped.

The finite custodian retains exact owned process/group handles and distinguishes
normal native exit before forced cleanup from exceptional termination. Failure to
verify absence stays unknown. No unrelated process scan/adoption is supported.

Watch and Timeline share the current control bar. Selecting an event freezes its
recorded inspection while activity continues; Follow latest returns to the current
tail. Prior-session pixels are not fetched from a replacement server. Source
images can fit the panel or retain original pixel size in a keyboard-scrollable
viewport; this presentation never requests a capture or changes control. Transport
feedback is rendered from session-scoped errors and current monotone stop facts,
so later confirmation cannot leave an earlier uncertainty alert unchanged.
One last identified Pause receiver with monotone stop facts preserves evidence outside the
current/previous view. It is explicitly separate from the current target; a receipt
alone cannot establish which opaque session is newer. Later matching status can
use that retained confirmation; reordered receipts cannot erase it or replace current diagnostics.

## Assurance and evidence

The [testing guide](../testing.md) routes viewer logic, loopback/composition,
package/driver and compiled-native tests. Actual browser/native visual inspection
is separate from parser/hash checks. [Operations](../runbook.md) route launch,
Pause and cleanup. The [production report](../acceptance/2026-10-29-computer-control.md)
owns actual play and retained browser timing limits; older
STOPPED/HISTORY or semantic-viewer reports are scoped historical evidence.

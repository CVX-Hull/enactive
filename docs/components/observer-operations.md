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
| [Custodian](../../tools/campaign_run.py) | Frozen admission validation, exact native target, store/server lifetime and final cleanup/accounting receipt. |
| [Preparation](../../tools/prepare_game.py) | Project-local windowed options, normal mouse input, wrapper/userdir and shared exclusion before changes. |
| [Build](../../tools/build_computer.py) | Current mechanical SDL adapter/fixture plus source/output provenance; no gameplay claim. |

## Projection and failure semantics

`GET /api/status` is passive `computer-status/1`; `/api/source/ID` serves current
session PNGs. Browser reads do not select a player store or create observations.
`POST /api/pause` accepts `{}` and bypasses actor/executor/DB waits. Authenticated
actor tools use `/api/tool`; source reads use `/api/player-source`. No CORS/public
exposure, semantic recovery controls or browser-issued actor handoff exists.

Report stop-requested separately from native-confirmed Pause. A stale image or
retained launch receipt is historical evidence, not current liveness. Player claims
are fallible, separately labelled data. Delivered events, process absence and host
completion do not certify a save or objective. Unknown input remains stopped.

The finite custodian retains exact owned process/group handles and distinguishes
normal native exit before forced cleanup from exceptional termination. Failure to
verify absence stays unknown. No unrelated process scan/adoption is supported.

## Assurance and evidence

The [testing guide](../testing.md) routes viewer logic, loopback/composition,
package/driver and compiled-native tests. Actual browser/native visual inspection
is separate from parser/hash checks. [Operations](../runbook.md) route launch,
Pause and cleanup. Current production real-game acceptance remains open; older
STOPPED/HISTORY or semantic-viewer reports are scoped historical evidence.

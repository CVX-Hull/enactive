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
| [Server](../../harness/server.py) | Selected `127.0.0.1` host/origin checks, bounded JSON, passive status/source/activity/investigation routes and independent Pause. |
| [Web viewer](../../web/) | Actual source presentation, mechanical versus player-claim labels, host/resource status and Pause feedback. |
| [Activity projection](../../harness/observer.py) | Disposable bounded host tail and read-only computer-record snapshot; explicit original links and coverage, no custody or second journal. |
| [Investigation export](../../tools/investigation.py) / [shared reader](../../web/investigation.js) | One-shot selected closed-case bundle; local import and recorded-only HTML use the same bounded passive renderer. |
| [Live snapshot adapter](../../tools/investigation_live.py) / [session attachment](../../web/investigation-session.js) | On-demand current-session evidence snapshot through a finite isolated read, staged validation and explicit refresh; no collector or actor authority. |
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

Watch, Timeline and Analysis share the current control bar. Selecting an event freezes its
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

## Investigation flow

Timeline can filter retained text/kinds and collapse explicit actor/request or
operation groups. It keeps selected evidence when it falls outside a filter;
filters cannot recover omitted history. Group spans use approximate recorded wall
time, not an inferred model state or causal trace.

Analysis automatically attaches an as-of snapshot of the serving session when
first opened. Refresh reads existing records through the injected finite adapter;
it never captures game pixels. Inspection stays frozen through activity and session
turnover until explicit attachment/import. Its timestamp and per-producer coverage
explain which current evidence is available. Older selected local bundles remain optional.
Validation,
indexing and PNG hashing run in a terminable worker with finite limits from the
[artifact contract](../contracts/observer-investigation.md). The same renderer
ships in a recorded-only HTML export with no network or current-target controls.
An import error or missing asset does not block independent current Pause. Imported
sessions never replace live status, source or custody, and offline HTML has no Pause.

The reader joins exact rows, approximate wall lanes, original selected images and
attributed assessments. Reverse references follow existing IDs; shared run IDs are
grouping evidence only. Timestamp points are distinct from measured spans. Interval
summaries union recorded request/tool wall spans and expose overlap/uncovered time;
they do not isolate inference, prove idle time or judge useful progress. Program
dispositions/child IDs and available version-level authoring/read IDs survive;
program bodies/raw diagnostics and missing preparation costs remain explicit gaps.
The live axis includes an explicitly unmeasured tail to snapshot completion, while
original event endpoints/unions remain unchanged. No collector, automatic diagnosis, annotation store or
game semantics is added.

## Assurance and evidence

The [testing guide](../testing.md) routes viewer logic, loopback/composition,
package/driver and compiled-native tests. Actual browser/native visual inspection
is separate from parser/hash checks. [Operations](../runbook.md) route launch,
Pause and cleanup. The [Watch/Timeline report](../acceptance/2026-10-29-spectator-watch-timeline.md)
owns linked investigation, actual same-page Pause/admission evidence and its limits.
The [production report](../acceptance/2026-10-29-computer-control.md) retains earlier native/player qualification; older
STOPPED/HISTORY or semantic-viewer reports are scoped historical evidence.

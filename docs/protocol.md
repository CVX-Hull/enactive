---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

<a id="bridge-and-guarded-play-contract"></a>

# Computer control and player contract

The sole current exact contract is [Computer control and player ports](contracts/computer-control.md).
It replaces native7/mission11, semantic gameplay commands, phase/identity admission,
legacy snapshots and old executable-memory import. Unsupported versions refuse;
there is no compatibility backend. [ADR006](decisions/006-computer-control-boundary.md)
explains the decision, and [migration](operations/migration.md) explains state treatment.

## Contract navigation

| Reader task | Current authority |
| --- | --- |
| Native packets, images, Pause and backpressure | [Native channel](contracts/computer-control.md#native-channel), [protocol code](../harness/computer/protocol.py) |
| Operations, actor custody, original collection and handoff | [Computer operations and custody](contracts/computer-control.md#computer-operations-and-custody), [runtime](../harness/computer/runtime.py) |
| Claims, sources, programs and bounded context | [Player knowledge and executable proposals](contracts/computer-control.md#player-knowledge-and-executable-proposals), [player package](../harness/player/) |
| Tool arguments | [Current tool descriptions/schemas](../harness/player_tools.py); `.venv/bin/python -m tools.configure_player_tools --describe` |
| Finite package and cleanup | [Campaign procedure](operations/campaign-run.md), [package validator](../tools/campaign_package.py) |

## Controller run ownership

The mechanical custodian owns one writer, exact native handles and original
resource limits. Per-actor bearer capabilities authorize input; memory, process
IDs and retained JSON cannot recreate them. Independent user Pause permanently
stops the run. Partial/unknown input stays charged and is never replayed.

## Integrated mission lifecycle

There is no harness game lifecycle. The player interprets all menus, creates or
loads a character, chooses Save and quits through ordinary controls. The harness
reports delivery and normal native exit before forced cleanup separately; it
never certifies a save or game success. Actor handoff is only custody/context
transfer, with no game-phase or identity requirement.

### Quiescent player replacement

The player selects context roots and summary with `player_handoff`. Canonical
issuance seals its actor. The player host settles only its direct originating handoff
or exact original collection; the driver verifies context digest and actual
old host/MCP group quiescence before a successor. Original limits persist.
The [player host contract](contracts/player-host.md) owns the substitutable
`player-host/2` invocation, telemetry, settlement and isolation rules.

## Transport and state

Native uses inherited nonblocking socket framing. HTTP binds `127.0.0.1`, accepts
bounded JSON and exact actor capabilities, and rejects cross-origin access.
The client gives each submission its ID before sending. `computer_result` and
`player_result` collect originals without effects; transport uncertainty proves
neither delivery nor nondelivery. MCP cancellation requests independent permanent
Pause before abandoning the await.

Current storage is fresh `computer-session/2` plus explicitly selected
`player-memory/1`. Immutable sources retain original PNG bytes and digest.
[Current data treatment](contracts/computer-control.md#responsibilities-and-current-data)
and [migration](operations/migration.md) own versions and historical-state handling.

## Designated campaign operator

One designated player, run by the selected player host, owns routine gameplay interpretation and choices.
The lead owns source, frozen admission, review and verification. Explorers and
reviewers send no game input. Advisers and programs are optional fallible aids;
the current route has no asynchronous semantic worker or hidden game-state feed.

## Historical contract navigation

The remaining pages in `contracts/` are superseded bookmarks for the earlier
native7/mission11 system. Each links its original accepted source and the current
replacement. They are not runnable current instructions or authority to import
old data. Historical acceptance reports retain their original tested scope.

<!-- Retained bookmarks for the coordinated contract migration. -->
<a id="lifecycle-action-preconditions"></a>
<a id="skill-request-binding-errors"></a>
<a id="selected-item-inspection-and-activity-composition"></a>
<a id="certified-request-admission-refusal"></a>
<a id="ordinary-discovery-and-procedure-data"></a>
<a id="explicit-operator-recovery"></a>
<a id="closed-loop-play-and-observations"></a>
<a id="passive-gameplay-records-and-evidence"></a>
<a id="passive-task-memory"></a>
<a id="bounded-injected-planner"></a>
<a id="passive-bounded-movement-skills"></a>
<a id="passive-waypoint-supervision"></a>

Earlier semantic lifecycle and tool bookmarks now route to the current
computer-control boundary described above. The remaining contract pages retain
their historical source links.

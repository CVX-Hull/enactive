---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Computer control and player contract

The exact contracts are [Computer control and player ports](contracts/computer-control.md),
the [player host](contracts/player-host.md) and [evaluation](contracts/evaluation.md).
Unsupported versions refuse; there is no compatibility backend.
[ADR006](decisions/006-computer-control-boundary.md) explains the boundary decision, and
[migration](operations/migration.md) explains state treatment. Other pages in
`contracts/` are superseded; [documentation](documentation.md#lifecycle-and-maintenance)
says how to read them.

## Contract navigation

| Reader task | Current authority |
| --- | --- |
| Native packets, images, Pause and backpressure | [Native channel](contracts/computer-control.md#native-channel), [protocol code](../harness/computer/protocol.py) |
| Operations, actor custody, original collection and handoff | [Computer operations and custody](contracts/computer-control.md#computer-operations-and-custody), [runtime](../harness/computer/runtime.py) |
| Claims, sources, programs and bounded context | [Player knowledge and executable proposals](contracts/computer-control.md#player-knowledge-and-executable-proposals), [player package](../harness/player/) |
| Tool arguments | [Current tool descriptions/schemas](../harness/player_tools.py); `.venv/bin/python -m tools.configure_player_tools --describe` |
| Finite package and cleanup | [Campaign procedure](operations/campaign-run.md), [package validator](../tools/campaign_package.py) |
| Interpretive run evaluation and the spectator view | [Evaluation records, metrics and spectator view](contracts/evaluation.md); rationale in [ADR008](decisions/008-evaluation-and-spectator.md). Nothing in it reaches the player or gates input. |

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
`player-host/3` invocation, telemetry, settlement and isolation rules.

The player keeps its ongoing user objective. Experiment quotas and final-actor
policy remain outside its guide, prompt, MCP results and program views. MCP emits
`player-computer-result/1` without global deadline/remaining data, plus
`player-error/2` and `player-transport/2`; canonical operation/HTTP records remain
unchanged. Programs require `player-program/2` with `view_schema:"program-view/4"`.

The driver owns bounded `player-control/1` stdin and admission-wide pending stop
identity. A successor declared with a pending ID waits for its matching command
before MCP connection or provider fetch. Optional finish-up and direct
`player_finish` settlement do not gate independent Pause, hard limits or owned
cleanup. Ordinary narration is not completion; stopping does not certify game
saving, paused state or application exit.

## Transport and state

Native uses inherited nonblocking socket framing. HTTP binds `127.0.0.1`, accepts
bounded JSON and exact actor capabilities, and rejects cross-origin access.
The client gives each submission its ID before sending. `computer_result` and
`player_result` collect originals without effects; transport uncertainty proves
neither delivery nor nondelivery. MCP cancellation requests independent permanent
Pause before abandoning the await.

Current storage is fresh `computer-session/1` plus explicitly selected
`player-memory/2`. Immutable sources retain original PNG bytes and digest.
[Current data treatment](contracts/computer-control.md#responsibilities-and-current-data)
and [migration](operations/migration.md) own versions and historical-state handling.

## Designated campaign operator

One designated player, run by the selected player host, owns routine gameplay interpretation and choices.
The lead owns source, frozen admission, review and verification. Explorers and
reviewers send no game input. Advisers and programs are optional fallible aids;
the current route has no asynchronous semantic worker or hidden game-state feed.

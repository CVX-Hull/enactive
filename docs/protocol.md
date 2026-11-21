---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Computer control and player contract

The exact contracts are [computer control and player ports](contracts/computer-control.md),
the [player host](contracts/player-host.md) and [evaluation](contracts/evaluation.md).
The [computer-control boundary decision](decisions/006-computer-control-boundary.md)
explains the rationale. The [migration procedure](operations/migration.md) governs
version and state handling.

## Contract navigation

| Reader task | Current authority |
| --- | --- |
| Native packets, images, Pause and backpressure | [Native channel](contracts/computer-control.md#native-channel), [protocol code](../harness/computer/protocol.py) |
| Operations, actor custody, original collection and handoff | [Computer operations and custody](contracts/computer-control.md#computer-operations-and-custody), [runtime](../harness/computer/runtime.py) |
| Hints, sources and handoff context | [Player knowledge and executable proposals](contracts/computer-control.md#player-knowledge-and-executable-proposals), [player package](../harness/player/) |
| Tool arguments | [Current tool descriptions/schemas](../harness/player_tools.py); `.venv/bin/python -m tools.configure_player_tools --describe` |
| Finite package and cleanup | [Campaign procedure](operations/campaign-run.md), [package validator](../tools/campaign_package.py) |
| Interpretive run evaluation and the spectator view | [Evaluation records and metrics](contracts/evaluation.md), [observer operations](components/observer-operations.md) |

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

The player supplies a summary with `player_handoff`. Canonical
issuance seals its actor. The player host settles only its direct originating handoff
or exact original collection; the driver verifies context digest and actual
old host/MCP group quiescence before a successor. Original limits persist.
The [player host contract](contracts/player-host.md#settlement-and-handoff) owns
settlement and handoff. The [computer-control contract](contracts/computer-control.md#computer-operations-and-custody)
owns the actor-facing projection and full operation records.

The driver carries a pending stop across actor replacement. Optional finish-up
and direct `player_finish` settlement operate independently of Pause, hard limits
and owned cleanup. See the [external-control contract](contracts/player-host.md#external-control).

## Transport and state

Native uses inherited nonblocking socket framing. HTTP binds `127.0.0.1`, accepts
bounded JSON and exact actor capabilities, and rejects cross-origin access.
The client gives each submission its ID before sending. `computer_result` and
`player_result` collect originals without effects; transport uncertainty proves
neither delivery nor nondelivery. MCP cancellation requests independent permanent
Pause before abandoning the await.

Each run opens a fresh computer session and can use an explicitly selected player
journal. Immutable sources retain original PNG bytes and digest.
[Current data treatment](contracts/computer-control.md#responsibilities-and-current-data)
and [migration](operations/migration.md) own versions and historical-state handling.

## Designated campaign operator

One designated player, run by the selected player host, owns routine gameplay interpretation and choices.
The lead owns source, frozen admission, review and verification. Explorers and
reviewers send no game input. The [curator runner](components/curator.md) starts
beside play only when [explicitly configured under supervision](operations/campaign-supervision.md#freeze-launch-and-inspect).

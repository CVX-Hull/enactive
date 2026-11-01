---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Current architecture

Enactive separates mechanical computer custody from player-owned interpretation.
The [overview](overview.md) owns capabilities and limits; the
[computer-control contract](contracts/computer-control.md) owns exact fields,
versions and failure behavior. Historical native7/mission11 contracts are replaced.

## Scope and responsibilities

![Current logical player and computer responsibilities.](diagrams/player.svg)

This current diagram answers “Who decides and who can stop input?” Boxes identify
logical responsibilities; arrows identify requests, results or user control.
[Editable source](diagrams/player.mmd). Its text equivalent is below.

| Responsibility | Owned state and authority | Component |
| --- | --- | --- |
| Deciding player / player host | Goals, visual interpretation, game choices and fallible claims; explicit provider/context/tools | [Player interface](components/player-interface.md) |
| Optional player services | Knowledge, corrections, source provenance, program lineage and bounded context; no custody | [Memory and learning](components/memory-learning.md) |
| Composition service | Connects player proposals to the computer port; retains service requests and context snapshots | [Execution](components/mission-execution.md) |
| Computer custodian | Exact child/socket/lock handles, serialized operations, original resources and actor capabilities | [Native control](components/native-control.md) |
| Observer / operator | Passive status/images, bounded linked recent activity, labelled player claims and independent permanent Pause | [Observer operations](components/observer-operations.md) |
| Game | Consumes ordinary SDL input and determines outcomes | Windowed prepared CDDA; no semantic engine bridge |

## Runtime and state

`tools/campaign_run.py` is the sole finite custodian. It validates a fresh frozen
`campaign-run/4` package and reserves exclusion before launch. `OwnedTarget` keeps
exact subprocess handles and passes an inherited shared-lock descriptor and a
nonblocking Unix socket to the SDL adapter. Native retains the shared lock for
its lifetime, including after the custodian loses its own reference.

The computer receive thread decodes bounded packets without writing files or
SQLite. The serialized runtime records intent and capacities before publication;
the custodian publishes PNGs/SQLite outside the native event loop. Failure at the
authoritative computer-store/source boundary permanently stops input;
restart cannot reconstruct custody from history. Passive observer read failures
instead report unavailable evidence and cannot change custody.
The source modules are [launch](../harness/computer/launch.py),
[channel](../harness/computer/channel.py), [runtime](../harness/computer/runtime.py)
and [store](../harness/computer/store.py).

The loopback [HTTP server](../harness/server.py) exposes passive spectator reads,
independent Pause and authenticated per-actor tools. The bounded
[activity projection](../harness/observer.py) reuses original host events and a
separate read-only computer snapshot; it owns no executor or durable journal.
The [application](../harness/application.py)
composes the computer port with optional player memory/program services. A
project-local stdio MCP adapter owns no writer, native child or provider key.
The selected [player host](contracts/player-host.md) owns model calls; the campaign
driver owns exact host/MCP group cleanup.

Fresh session stores live under `.runtime/computer-sessions/`. A selected
`player-memory/1` store may span fresh native-child sessions. Old runtime formats
remain inert history; no current reader imports executable old libraries.

## Action and recovery views

### What happens when the agent acts?

The client assigns an operation ID before HTTP submission. The custodian validates
the entire basic sequence, reserves original resources and serializes dispatch.
The adapter reports exact delivery and captures actual presented pixels. Keys and
text have no image-age, equality or game-phase predicate. Pointer actions bind
mechanical geometry and a source actually issued to that actor. Delivered input
is not game success. [Action source](diagrams/action.mmd).

### How do I recover control?

Pause sets the permanent stop event before executor/DB work and sends through a
separate bounded path; failure to send closes the write side to signal EOF.
Real native input takes precedence and fences automation. Partial or unknown
input remains charged and unreplayed; collect the original result. There is no
Resume/rearm or phase-based recovery. Native manual interaction can still recover
the application. [Pause procedure](operations/pause-timeout.md).

## Observation and deployment boundaries

The supported deployment is a local Mac with a prepared windowed CDDA app and
project userdir. Captures contain the actual default-renderer presentation and
original geometry/time; repeated pixels remain valid. The native adapter sends
bounded image bytes over its inherited socket. File publication is outside its
callbacks; this does not promise resistance to upstream save I/O, PNG CPU or
arbitrary OS hangs. The original publication-stall cause remains unknown.

## Game-family portability

The computer package imports no game interpretation. Shared player claims,
programs and context consume only the computer port and explicit player data.
CDDA-specific preparation stays outside that package. This separation is a source
boundary; actual portability to a second game remains unqualified.

## Separate recovery and memory boundaries

Remembered sources/claims and old process IDs never restore custody. Player
corrections retain prior records and contradictions. Program failures/yields leave
basic input available if mechanical custody is healthy. Mechanical Pause or
uncertainty cannot become a resumable handoff.

## Bounded planning without execution authority

Local JavaScript sees an explicit image view and optional player interpretation.
It proposes the same basic controls; the coordinator alone submits them under
original deadlines/capacities. Candidate advice and applicability are fallible
player data. No semantic supervisor or planner is required for ordinary control.

## Run ownership and operator takeover

Handoff persists a canonical bounded context, then seals the actor. A sealed token
can collect originals and read retained knowledge, but cannot capture anew or
mutate. Only the driver, after canonical issuance/context verification and actual
old host/MCP group quiescence, can mint a successor under original limits. It
requires no save, menu or identity check. [Run procedure](operations/campaign-run.md).

## Coordinated change

One current set is `computer-wire/1`, request/target/receipt `/2`,
`computer-session/2`, `computer-operation/1`, `computer-source/1`,
`player-memory/1`, `player-record/1`, `player-program/1`, `program-view/3`,
`player-handoff/2`, `player-host/4` and `campaign-run/4`. The exact contracts own the complete set.
[Migration](operations/migration.md) rejects old stores before effects and preserves
artifacts/saves as history. Rollback closes writers and selects a coherent earlier
source/data deployment; mixed readers and replay are unsupported.

## Change boundaries and verification

### Responsibility assurance

| Changed boundary | Evidence to inspect and limit |
| --- | --- |
| Packet/input/custody | Strict schema, socket/backpressure, writer/deadline and uncertainty assertions; [native control](components/native-control.md#assurance-and-evidence) adds compiled behavior. |
| Memory/program/context | Pure player and composition assertions for provenance, helper fault isolation and original child IDs; [memory](components/memory-learning.md#assurance-and-evidence). |
| Host/driver | Contract conformance and actual adapter/MCP fixtures, origin-bound handoff, attempt accounting and exact group quiescence; [player interface](components/player-interface.md#assurance-and-evidence). |
| Spectator/operation | Actual images, mechanical versus claim labels and independent Pause; [observer](components/observer-operations.md#assurance-and-evidence). |

The [testing guide](testing.md) selects lanes. [Production outcome evidence](acceptance/2026-10-29-computer-control.md)
covers actual basic input, useful stock, conditional scouting, succession and
Save/new-child reload/normal ending. Source fixtures alone cannot qualify those
effects; useful cadence, general safe navigation and survival remain separate.

<!-- Retained bookmarks for the coordinated contract migration. -->
<a id="passive-skill-verification"></a>
<a id="passive-task-supervision"></a>

Earlier semantic lifecycle and tool bookmarks now route to the current
computer-control boundary described on this page; the [protocol](protocol.md)
links the replacement contract and historical references.

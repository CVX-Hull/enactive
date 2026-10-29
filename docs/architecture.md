---
owner: maintainer
review_trigger: Responsibility, authority, state ownership, supported behavior or deployment changes
status: active
---

# Current architecture

Enactive separates the player who decides, the software that executes and records,
the game that determines outcomes, and the user who retains control. This is the
system map. Component views explain internals; [protocol](protocol.md) and schemas
own exact contracts. [Overview](overview.md) owns capabilities and limits.
Dated reports preserve observations, not current architecture instructions.

## Scope and responsibilities

![Current deciding player, memory, mission writer, native game and spectator.](diagrams/player.svg)

This current logical view answers “Who decides, who executes, and who can stop it?”
Boxes are responsibilities, not mandatory separate model tiers or processes.
Solid arrows carry decisions/evidence; dotted arrows carry fallible background
advice. [Editable source](diagrams/player.mmd).

| Responsibility | What it owns | Zoom into the component |
| --- | --- | --- |
| User / engineering lead | Product constraints / design, admission, integration and verification | [Charter](charter.md), [workflow](project-management.md); no routine lead tactics or curation |
| Deciding player and ingress | Generic Pi host with explicit model/context/tools; player owns plans, visible interpretation and intent, software composes canonical requests and bounded context | [Player interface](components/player-interface.md) |
| Mission execution | One writer/queue, original scope and accounting, phases, feedback and lifecycle | [Mission execution](components/mission-execution.md) |
| Evidence, memory and learning | Retained sources, fallible claims/Work/procedures and asynchronous proposals | [Memory and learning](components/memory-learning.md) |
| Controller and native integration | Exact input custody, receiver/deadline fences, visible captures, Pause and takeover | [Native control](components/native-control.md) |
| Spectator and host operations | Actual frames, passive status/cost projections, isolated setup and retention | [Observer and operations](components/observer-operations.md) |

Component pages identify internals, owned state, interfaces, failure paths, source
and tests. Descend where the decision needs it; [documentation](documentation.md)
explains the review hierarchy. Logical decomposition does not claim the large
source modules have been split.

## Runtime and state

One local Mac game/controller is the validated deployment. The project-local
stdio MCP process adapts local HTTP ingress; it is not another executor.
Server/CLI assemble MissionRuntime, which serializes mission mutations and uses
the controller. The native bridge runs inside CDDA and commits normal engine/UI
input on its game thread. A separately assigned adviser may compute during play,
without input authority. Role rules are procedural, not OS isolation.

SQLite owns canonical domain records; retained files own indexed source/frame
evidence; caches hold bounded derived views. Controller leases and private phases
exist only in their owning process. Historical records, actor names and JSON
cannot reconstruct authority. Use configured DB/OS/library contracts, adding only
demonstrated domain guards rather than another persistence/recovery framework.

## Action and recovery views

### What happens when the agent acts?

The player chooses intent, informing evidence and finite scope. One writer
retains intent before publication, dispatches under current controller/native
fences, records the actual result and returns evidence. Ordinary input is
foundational; semantic skills and player-authored bounded programs are optional
aids. Delivered input is not proof of objective success.
[Execution flow and internals](components/mission-execution.md).

### How do I recover control?

Pause stops subsequent remote dispatch and native input latches takeover.
Neither undoes committed input nor guarantees activity interruption. Unknown
delivery stays charged and unreplayed; supported collection/reconciliation retain
uncertainty. Restart restores history, never a lease.
[Control view](components/native-control.md), [runbook](runbook.md),
[exact recovery contract](contracts/operator-recovery.md#explicit-operator-recovery).

## Observation and deployment boundaries

Actual rendered frames and explicitly visible metadata inform play, without hidden
state or save reading. The loopback spectator is not qualified for public exposure.
Launch stays windowed with explicit project userdir; new dependencies, caches,
builds and outputs stay local or in recorded owned temporary builds. Background
launch is a child-process hint, not proof OS focus cannot change.
[Operational boundaries](components/observer-operations.md).

## Game-family portability

The [charter](charter.md) requires applicability across CDDA-class games. Current
qualification is CDDA on this Mac, not a delivered universal plugin interface.

The owner-selected [computer-control direction](decisions/006-computer-control-boundary.md)
requires the harness to expose only basic computer observation/control. Game
meaning and optional helpers belong entirely to the playing system. The table
and coupling inventory below describe **current implementation**, which has not
yet made that coordinated cutover; they are not approval to extend semantic
input gates. A game menu or failed player routine should not itself revoke input
custody in the target design.

| Shared design responsibility | Game integration responsibility |
| --- | --- |
| Planning, ordinary exploration and interpretation | Visible observation and ordinary input in the actual engine/UI |
| Source-linked memory, revisable procedures and asynchronous advice | Game/version/configuration applicability and optional observed semantics |
| One writer, finite costs, uncertainty and request/result correlation | Supported receiver, custody and timing attestations |
| Campaign/evidence review and spectator presentation | Game-specific identity, persistence and outcome evidence |

Shared memory consumes passive repository/source ports. The mission adapter owns
request admission/provenance; the CDDA adapter projects literal scene facts and
validates world/character interpretation. Shared time arithmetic consumes explicit
projected seconds and authenticated adjacent endpoints. CDDA's adapter owns turn
conversion, same-turn reload continuity and retained reference integrity.

Menu categories, inventory/count provenance, coordinates and Save/identity
transitions remain integration concepts in native classification, MissionRuntime,
mission contracts/ledger, lifecycle proofs and preparation. `gameplay/2` EvidenceRef
and `cdda-visible/1` remain the current CDDA binding's formats; these are not a
universal observation schema. The source separation preserves current persisted
representations and adds neither another executor nor a speculative game framework.
[Memory and source ports](components/memory-learning.md#internal-responsibilities)
and [time projection](contracts/gameplay-evidence.md#binding-projections) identify
the concrete interfaces. Independently shaped fixtures exercise the seam; actual
portability still needs another real integration under
[#191](https://github.com/CVX-Hull/enactive/issues/191).
A seven-day CDDA result would not prove family-wide support.

## Separate recovery and memory boundaries

Recovery retains original dispatch custody and reconciles effects. Memory retains
fallible historical assertions and procedure candidates. Neither authorizes input.
Reflection does not introduce a required critic pause; the player adopts advice
and the lead stays outside routine curation. Software binds procedure metadata,
exposes compact snapshot-indexed candidates and submits explicitly selected
originals. Finite horizon/age allocation and optional software idle waiting keep
routine learner bookkeeping off the deciding path. These source capabilities do
not establish graphical cadence or useful learning; the
[offline execution experiment](acceptance/2026-10-24-execution-first-offline.md)
keeps those evidence lanes separate.
[Memory/learning flow](components/memory-learning.md), [native control](components/native-control.md).

## Bounded planning without execution authority

The injected planner port and TaskMemory/waypoint libraries are passive study
components. They return candidates and own no controller lease or live task/planner
endpoint in MissionRuntime. No concrete planner provider is connected to that
service. They are not a generic autonomous campaign executor.
[Exact passive contract](contracts/injected-planner.md#bounded-injected-planner).

## Passive skill verification

The offline movement verifier proposes an input and consumes correlated feedback;
the caller owns dispatch. It shares the pure policy with controller walk. Current
missions also compose skills through their writer.
[Passive contract](contracts/movement-skills.md#passive-bounded-movement-skills) and
[diagram](diagrams/skill.svg) distinguish proposal/verification from live authority.

## Passive task supervision

The waypoint supervisor combines passive planning, memory and movement for one
waypoint/return study. It owns no input capability and cannot silently become the
live player. [Contract](contracts/movement-skills.md#passive-waypoint-supervision) and
[diagram](diagrams/supervisor.svg) retain that scope.

## Run ownership and operator takeover

One exact in-process controller capability belongs to MissionRuntime. Competing
ordinary writers reject; cached status and Pause remain available. Internal
rotation cannot erase user Pause.
[Ownership view](components/native-control.md) leads to the
[exact contract](contracts/controller-ownership.md#controller-run-ownership).

## Coordinated change

Apply [S-MIGRATION](standards/migration.md#s-migration-one-current-contract-coordinated-migration):
one current contract; coordinate producers, consumers, state, fixtures and guidance.
No compatibility shim or downgrade. Distinct version numbers describe distinct
contracts; [protocol](protocol.md) owns the current reference. Historical artifacts
remain evidence, not supported runtime input.

## Change boundaries and verification

### Responsibility assurance

Use this map to ask what could go wrong, which responsibility must prevent or
expose it, and what evidence is worth inspecting. Each component's assurance view
links current invariants/contracts, existing controls and representative evidence
with its limits. It is a review path, not a complete risk inventory or a statement
that every possible failure has been tested.

| Consequence to challenge | Responsible view and evidence path |
| --- | --- |
| The player acts on the wrong source, or uncertain input is replayed | [Player interface](components/player-interface.md#assurance-and-evidence): selected intent, context and original collection |
| Costs or consent are renewed, or history becomes live authority | [Mission execution](components/mission-execution.md#assurance-and-evidence): one writer, original accounting, phase and lifecycle ownership |
| Pause/takeover fails to fence input, or a capture is mistaken for eligibility | [Native control](components/native-control.md#assurance-and-evidence): host/receiver fences and separate native qualification |
| Unsupported memory or learned procedures become trusted facts or another executor | [Memory/learning](components/memory-learning.md#assurance-and-evidence): support, bounded programs and advisory lineage |
| A historical frame/receipt looks current, or host/build evidence overstates an outcome | [Observer/operations](components/observer-operations.md#assurance-and-evidence): passive projections, owned resources and outcome limits |
| Incorrect guidance or a passing source check is treated as acceptance | [Engineering assurance](testing.md#engineering-assurance): structural checks, semantic review and exact protected publication |

The [testing guide](testing.md#responsibility-assurance) explains native test
metadata and focused selection. Component maintainers own these associations with
the lead under C-REVIEW/C-MAINTENANCE; exact rules remain in their contracts and
assertions. Compiled fixtures, actual native behavior, campaigns and manual review
are different evidence lanes. Follow their stated scope rather than treating a
pytest group as proof of the whole responsibility.

Scope work from the affected system responsibility down to components, contracts,
state/callers, code, tests and procedures. Review the highest changed boundary
before committing its implementation. An unchanged parent needs a link and impact
statement, not recursive approvals. Select checks from consequence and uncertainty
under the [assurance tiers](workflows/review.md#risk-based-assurance).

Import Linter checks declared dependency directions; protocol/document checks catch
selected drift. They do not prove semantic truth. Source tests, native builds,
real gameplay and protected publication are separate lanes. Changed native support
needs relevant matching native evidence; document reorganization does not
requalify a game. [Control map](controls.md).

Consequential rationale remains in the [native platform](decisions/001-native-platform.md)
and [local contract](decisions/002-local-contract.md) ADRs. Prior briefs and reports
remain history; live outcomes and remaining work belong in
[GitHub](https://github.com/users/CVX-Hull/projects/2).

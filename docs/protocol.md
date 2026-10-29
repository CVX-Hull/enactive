---
owner: maintainer
review_trigger: Native bridge, controller, input, observation or skill change
status: active
---

# Bridge and guarded-play contract

Protocol version: 7.

The isolated [computer-control proof](changes/070-computer-control-proof.md)
has its own exact experimental shapes and no product-CLI route. Its
[evidence](acceptance/2026-10-29-basic-computer-control.md) does not change the
current versions below; #176 must replace all current producers/readers together.

This index routes to exact current contracts supporting [architecture](architecture.md).
Use the component views for understanding before this exact reference:
[player tools](components/player-interface.md), [mission phases](components/mission-execution.md),
[memory/advice](components/memory-learning.md), [native control](components/native-control.md)
and [observer/operations](components/observer-operations.md). Select the relevant
section below; routine contributors and players need not read this whole reference.
Authority rules are [S-PROTOCOL](standards/protocol.md#s-protocol-command-and-observation-authority).
Current source is native7/mission11/ledger13/archive6, with procedure/3,
campaign-memory/6, reflection/3 and program-view/2; gameplay/2 is unchanged.
[ADR006](decisions/006-computer-control-boundary.md) selects a future basic
computer-control boundary with game semantics in the playing system. The current
versions and contracts below remain implemented until their coordinated migration;
this index must not be read as the target architecture already being delivered.
Matching native7 marker qualification is a separate required lane from the
historical native6 ordinary-input/normal-lifecycle evidence in
[capture001](acceptance/2026-10-22-native-capture-preconditions.md). That old run
has capture-name churn but no checked PNG drift; it does not qualify this new
marker boundary. Persistent pixel drift and the retained-capture commit race
remain source-tested, not natively exercised.
[Learning006](acceptance/2026-10-22-discovery-learning-sixth-attempt.md)
and [native001](acceptance/2026-10-22-native-save-refresh.md) provide bounded
graphical qualification; wider input/geometry and the full independent campaign
retain their explicit limits. Dated native5 and earlier results retain their exact
scopes. Portable checks do not prove native engine behavior.

Unsupported versions and alternate response shapes are rejected. Startup validates
stored admissions, claimed requests and any response before restoring uncertainty;
it never converts old records. A dispatched response without its current-format
input identity blocks startup instead of fabricating a synthetic request. An offline
migration must preserve uncertainty and cannot grant authority or replay inputs.
See [coordinated migration](operations/migration.md#coordinated-migration).

Mission/11 and ledger13 migrate all current producers, callers and persisted readers
together. Earlier mission versions, ledger7 and its old untyped effect shape reject
without conversion. Retain old mission artifacts and saves as evidence; only a
separately admitted current mission can start anew. Migration never resets input
costs, renews a stopped attempt or restores execution authority.

## Contract navigation

Choose the interface needed for the reader task:

| Task | Current contract |
| --- | --- |
| Implement initial Load and adopt identity | [Launch](contracts/mission-admission.md#owned-launch-and-initial-load-admission), [transitions and menu dismissal](contracts/lifecycle-create-load.md), [adoption](contracts/lifecycle-preconditions.md#normal-identity-adoption-and-historical-proof) |
| Collect an uncertain request | [Player transport](contracts/player-transport.md), [delivery reconciliation](contracts/delivery-reconciliation.md) |
| Replace a player | [Handoff issuance](contracts/handoff-issuance.md), [successor Claim/readmission](contracts/handoff-issuance.md#successor-context-claim-and-readmission) |
| Choose ordinary input and inspect its outcome | [Input applicability](contracts/ordinary-input.md), [delivery](contracts/ordinary-delivery.md), [prompt observation](contracts/operation-observation.md) |
| Recover explicit operator control | [Recovery](contracts/operator-recovery.md) |

## Controller run ownership

- [Controller run ownership](contracts/controller-ownership.md).

## Integrated mission lifecycle

- [Player Claims and source grounding](contracts/player-claims.md).
- [Player transport and original result collection](contracts/player-transport.md).
- [Player snapshots, detail and image presentation](contracts/player-snapshots.md).
- [Integrated mission lifecycle](contracts/mission-admission.md).
- [Operation entry refresh and ordinary prompt observation](contracts/operation-observation.md).
- [Owned normal exit and menu cleanup](contracts/lifecycle-exit.md).
- [Creation, Load transitions and initial menu dismissal](contracts/lifecycle-create-load.md).
- [Lifecycle action preconditions](contracts/lifecycle-preconditions.md).
- [Skill request binding errors](contracts/request-binding.md).
- [Selected item, inspection and activity composition](contracts/item-inspection.md).
- [Quiescent player replacement](contracts/handoff-issuance.md).
- [Mission CLI, observation deadline and admission gate](contracts/mission-status.md#mission-cli-observation-deadline-and-admission-gate).
- [Unknown delivery collection and reconciliation](contracts/delivery-reconciliation.md).

### Lifecycle action preconditions

Read [Lifecycle action preconditions](contracts/lifecycle-preconditions.md#lifecycle-action-preconditions).

### Skill request binding errors

Read [Skill request binding errors](contracts/request-binding.md#skill-request-binding-errors).

### Selected item, inspection and activity composition

Read [Selected item, inspection and activity composition](contracts/item-inspection.md#selected-item-inspection-and-activity-composition).

### Quiescent player replacement

Read [Quiescent player replacement](contracts/handoff-issuance.md#quiescent-player-replacement).

## Transport and state

- [Certified request admission refusal](contracts/player-transport.md#certified-request-admission-refusal).
- [Ordinary discovery and procedure data](contracts/procedure-programs.md).
- [Ordinary direct input and source applicability](contracts/ordinary-input.md).
- [Ordinary delivery receipts and observation continuation](contracts/ordinary-delivery.md).
- [Historical procedure and advisory import](contracts/historical-import.md).
- [Asynchronous reflection and advice](contracts/advisory-reflection.md).
- [Native commands, visible observations and boundaries](contracts/native-observations.md).

### Certified request admission refusal

Read [Certified request admission refusal](contracts/player-transport.md#certified-request-admission-refusal).

### Ordinary discovery and procedure data

Read [Ordinary discovery and procedure data](contracts/procedure-programs.md#ordinary-discovery-and-procedure-data).

## Explicit operator recovery

- [Explicit operator recovery](contracts/operator-recovery.md).

## Designated campaign operator

- [Designated campaign operator](contracts/mission-admission.md#designated-campaign-operator).

## Closed-loop play and observations

- [Closed-loop play and observations](contracts/gameplay-evidence.md#closed-loop-play-and-observations).

## Passive gameplay records and evidence

- [Passive gameplay records and evidence](contracts/gameplay-evidence.md).

## Passive task memory

- [Passive task memory](contracts/injected-planner.md#passive-task-memory).

## Bounded injected planner

- [Bounded injected planner](contracts/injected-planner.md).

## Passive bounded movement skills

- [Passive bounded movement skills](contracts/movement-skills.md).

## Passive waypoint supervision

- [Passive waypoint supervision](contracts/movement-skills.md#passive-waypoint-supervision).

The [proposed computer-control replacement](contracts/computer-control.md) is the
reviewed #176 implementation target; it does not add a second supported runtime.

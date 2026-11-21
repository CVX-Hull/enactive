---
owner: lead
review_trigger: Execution composition, mechanical custody, actor handoff or close-out changes
status: active
---

<a id="mission-execution-one-writer-several-bounded-responsibilities"></a>

# Execution: one mechanical writer and optional player services

Execution composes one [ComputerRuntime](../../harness/computer/runtime.py) with optional player
services through [Application](../../harness/application.py). The
[current contract](../contracts/computer-control.md) owns exact interfaces and
[architecture](../architecture.md) owns system relationships.

## Internal responsibility and state map

| Responsibility | Authority and retained state |
| --- | --- |
| Mechanical writer | Validates complete basic sequences, reserves original resources before publication, serializes dispatch and retains exact operation/native IDs. |
| Composition | Serializes playing-service calls, checks actor authority again after waiting, lazily registers explicitly referenced images and retains service request IDs. |
| Context/handoff | Writes canonical immutable summary hint before sealing; snapshot is data, not a capability. |
| Campaign custodian/driver | Own exact native and host handles, validate old-host quiescence and mint a successor only under original limits. |

The loopback server/MCP adapter are transports, not additional writers. HTTP
submissions carry client-assigned IDs. Duplicate collection never redispatches.
Mechanical operation states are pending/completed/refused/partial/unknown/sealed;
none is a game-phase or task-success predicate.

## Feedback and discovery

The player interprets actual images and selects basic controls. It can report
fallible hints for later curation; no game-semantic eligibility handler or
structured engine fact is injected. Unknown or partial input stops further input.
[Memory and learning](memory-learning.md) describes the journal and delivery.
Configured estimates, provider-reported cost, actual HTTP attempts and invoices
stay distinct. Useful cadence and causal learning benefit require authentic outcomes.

## Lifecycle and change review

The harness has no create/load/save/menu/identity/Finish commands. These are
player-selected ordinary controls and player-owned claims. Native exit zero is
sampled before forced cleanup and reported separately from save/success.
Actor handoff requires no game-phase, source-checkpoint or identity condition.
It requires no outstanding/uncertain input or permanent Pause, a canonical
snapshot/issuance and actual old host/MCP quiescence before successor capability.

Changes across computer/player/custodian ports migrate callers, stores and
operations together; unsupported old formats reject before effects. No memory or
handoff record restores authority after restart. [Migration](../operations/migration.md).

## Assurance and evidence

Tests cover distinct custody, composition, journal, transport and cleanup boundaries.
Check the assertions against the changed invariant. Fixtures do not qualify real game
usefulness or save/reload/ending. Those outcomes and their limits are in the
[production report](../acceptance/2026-10-29-computer-control.md).

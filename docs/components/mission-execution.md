---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

<a id="mission-execution-one-writer-several-bounded-responsibilities"></a>

# Execution: one mechanical writer and optional player services

The old MissionRuntime and semantic lifecycle are retired. Execution now composes
one [ComputerRuntime](../../harness/computer/runtime.py) with optional player
services through [Application](../../harness/application.py). The
[current contract](../contracts/computer-control.md) owns exact interfaces and
[architecture](../architecture.md) owns system relationships.

## Internal responsibility and state map

| Responsibility | Authority and retained state |
| --- | --- |
| Mechanical writer | Validates complete basic sequences, reserves original resources before publication, serializes dispatch and retains exact operation/native IDs. |
| Composition | Serializes playing-service calls, checks actor authority again after waiting, lazily registers explicitly referenced images and retains service request IDs. |
| Local program coordinator | Sends program proposals through the same computer callback; retains child IDs before effects and passes the original deadline. |
| Context/handoff | Writes canonical immutable knowledge snapshot before sealing; snapshot is data, not a capability. |
| Campaign custodian/driver | Own exact native and host handles, validate old-host quiescence and mint a successor only under original limits. |

The loopback server/MCP adapter are transports, not additional writers. HTTP
submissions carry client-assigned IDs. Duplicate collection never redispatches.
Mechanical operation states are pending/completed/refused/partial/unknown/sealed;
none is a game-phase or task-success predicate.

## Programs, feedback and organic discovery

The player interprets actual images and authors optional JavaScript procedures.
`ProgramRunner` consumes a real capture per step, evaluates a bounded proposal and
uses the same basic control port. Returned images can feed the next step directly.
No game-semantic eligibility handler or structured engine fact is injected.
Helper failure/yield leaves direct input usable if mechanical custody is healthy;
unknown/partial input stops further input. [Memory/program component](memory-learning.md).

## Local feedback cost

Program CPU/state/heap/time and child-operation budgets are bounded independently
of Pi requests. A local program does not make an inference call each step.
Configured reservations, actual HTTP attempts and invoices stay distinct. Useful
whole-player cadence and causal learning benefit require authentic outcomes,
not loop speed or packet timings.

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

[Runtime](../../tests/test_computer_runtime.py), [application](../../tests/test_player_application.py),
[program](../../tests/test_player_programs.py), [MCP](../../tests/test_pi_player_host.py)
and [campaign](../../tests/test_campaign_run.py) assertions cover distinct custody,
composition, proposal, transport and cleanup boundaries. Check actual assertions
against the changed invariant; fixtures do not qualify real game usefulness or
save/reload/ending. Production real-game acceptance remains open.

<!-- Retained bookmarks for the coordinated contract migration. -->

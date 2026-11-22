---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Operate, recover and retain evidence

Every run starts from [setup](setup.md) and a fresh frozen package, under the current
[computer-control](contracts/computer-control.md) and
[player-ports](contracts/player-ports.md) contracts. One mechanical writer holds
[custody](operations/run-custody.md) through per-actor capabilities; no other producer
sends input, and no history rebuilds authority. The player interprets the game, and the
lead owns admission, source and review.

## Tasks

| Task | Procedure | Know first |
| --- | --- | --- |
| Prepare, launch and close a finite run | [Finite run](operations/campaign-run.md) | One designated player plays, run by the frozen player host, and hands off only to another actor ([assignment](operations/run-custody.md#designated-campaign-operator)) |
| Check what the player and lead may do | [Player ownership](operations/run-custody.md#permissions-and-player-ownership) | The player owns routine choices |
| <a id="start-and-observe"></a>Start the target and watch it | [Start and observe](operations/start-observe.md) | Prepared windowed target, explicit project userdir, fresh package and actual spectator images |
| Supervise a test | [Finite-test supervision](operations/campaign-supervision.md) | Adds Pause, an independent custody deadline and owned wrapper cleanup outside the player context. Nobody is required to watch |
| <a id="bounded-player-host-activation"></a>Start the player host | [Host activation](operations/player-host.md#bounded-player-host-activation), under the [player host contract](contracts/player-host.md) | Host adapter, MCP, context and route inputs are frozen and explicit. No coding agent or resumed host is a fallback |
| Use the basic computer tools | [Player tool results](operations/player-tool-results.md) | Collect an uncertain operation under its original ID |
| Pause, or handle a timeout | [Pause and timeout](operations/pause-timeout.md) | Pause is permanent and independent: no rearm, no replay of uncertain input |
| Recover by hand | [Manual recovery](operations/pause-timeout.md#operator-recovery) | Use the native application. Pause cannot undo delivered events or game activities |
| Run curator sessions | [Curator hosts](operations/curator-hosts.md), [shadow session](operations/curator-shadow-run.md) and [boundary grooming](operations/curator-hosts.md#post-admission-boundary-grooming) | The [curator contract](contracts/curator.md) owns formats and publication |
| Accept native behavior | [Native acceptance](operations/native-acceptance.md) | Compiled mechanics and game outcomes are recorded separately. The [production report](acceptance/2026-10-29-computer-control.md) owns scoped outcomes and remaining gaps |
| <a id="evidence-retention-and-cleanup"></a>Keep evidence and clean up | [Evidence retention](operations/evidence-cleanup.md#evidence-retention-and-cleanup) | Use current custodian and driver receipts for exact owned process cleanup. Preserve failed chains and original binaries and configuration |
| Migrate a format | [Migration](operations/migration.md) | Refuse old formats before effects, keep inert history, select fresh stores and roll back only as a coherent deployment |
| Set up a coding agent | [Coding-agent hosts](operations/coding-agents.md) | Maps instructions, roles, gameplay command allowances and the optional player MCP entry |
| Choose a delegate | [Choosing a model](operations/model-routing.md), [delegate profiles](operations/delegate-profiles.md) | The lead chooses for each task from both |

Commands in historical artifacts are not executable instructions.

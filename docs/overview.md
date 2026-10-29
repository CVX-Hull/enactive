---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Project overview

## What we are building

Enactive lets a designated agent play CDDA-class survival/roguelike games from
visible computer observations while a user watches and can stop automation.
The [charter](charter.md) owns purpose and constraints. CDDA is the first actual
target; no second game or unattended survival service is qualified.

The current source uses a basic computer-control boundary. The harness provides
actual PNGs, mechanical window geometry, key/text/pointer/wait, exact operation
collection, one writer and original limits. It contains no game-phase, menu,
activity, item or character-identity eligibility checks. The playing system owns
all interpretation, save/load choices, plans, quantities, Work and success claims.
Optional memory and local programs can help; ordinary input remains available
when a helper fails and mechanical custody is healthy.

## How it works

![Current logical responsibilities: one player, optional knowledge and one mechanical custodian.](diagrams/player.svg)

This current logical diagram answers “Who decides, who sends input and who can
stop it?” Boxes are responsibilities, not separate required models. Arrows carry
requests, evidence or labelled control. The player interprets pixels; the
custodian serializes basic actions through the SDL adapter; the game determines
effects. The user can Pause independently. Memory contains fallible player claims
and never grants custody. [Editable source](diagrams/player.mmd).

The [generic Pi host](components/player-interface.md) is mandatory. The selected
finite configuration is OpenRouter / Fireworks US / DeepSeek Flash1017 at medium
effort. Its exact route, metadata, context and limits are frozen per run; this
selection is not a claim of model quality or provider performance.

The [architecture](architecture.md) explains ownership, the
[player guide](player-guide.md) supplies compact working context, and the
[computer-control contract](contracts/computer-control.md) owns exact interfaces.

## What works and what the evidence means

| Boundary | Current scope and limit |
| --- | --- |
| Mechanical control | Production source implements actual images, basic input, original IDs, independent permanent Pause and owned cleanup. Real-game acceptance of this cutover has not occurred. |
| Player services | Optional typed claims/Work/corrections, image provenance, bounded JavaScript programs and immutable handoff context are implemented. Their usefulness must be assessed in authentic play. |
| Actor replacement | A sealed actor and actual host/MCP quiescence can admit one fresh successor under original limits. No game menu, save or identity condition grants authority. |
| Earlier CDDA play | [Organic corrected-program play](acceptance/2026-10-28-organic-play.md), [endpoint comparison](acceptance/2026-10-28-endpoint-gameplay.md) and [computer proof](acceptance/2026-10-29-basic-computer-control.md) retain their tested source/route and failures. They do not qualify this production boundary. |
| Remaining outcomes | Useful apparent cadence, causal learning benefit, independent seven-day survival, second-game control, broader geometry, Unicode/IME and actual-human takeover qualification remain open. |

Delivered means SDL events were handed over. It does not mean the application
consumed them, saved a character or achieved an objective. Exact receipts,
original PNGs and player claims stay distinct. Unknown or partial input permanently
stops further input and is collected by its original ID without replay.

## How development reaches acceptance

[Development-first delivery](workflows/development.md#development-first-delivery)
uses focused checks and coherent committed checkpoints for authentic play.
Source tests, compiled native interoperability, actual game outcomes, independent
review and protected CI are separate evidence lanes. A fixture cannot substitute
for failed gameplay. Keep every failed or abandoned chain and its original limits.
[Work](work.md) links evidence; GitHub owns execution and remaining gates.

## Current direction and decisions

[ADR006](decisions/006-computer-control-boundary.md) explains the selected boundary;
[#176](https://github.com/CVX-Hull/enactive/issues/176) owns its integrated delivery,
[#287](https://github.com/CVX-Hull/enactive/issues/287) the mechanical implementation,
and [#288](https://github.com/CVX-Hull/enactive/issues/288) the playing system.
The [cutover brief](changes/071-computer-control-cutover.md) retains the delivery
scope. [#164](https://github.com/CVX-Hull/enactive/issues/164),
[#177](https://github.com/CVX-Hull/enactive/issues/177) and
[#145](https://github.com/CVX-Hull/enactive/issues/145) own cadence, learning and
independent survival outcomes. These are separate claims, not implied by migration.

## How you stay in control of the project

Use the [Project](https://github.com/users/CVX-Hull/projects/2) for priorities,
[work](work.md) for evidence, and the [documentation map](documentation.md) for
review. The lead owns design, integration and verification; the deciding player
owns routine tactics and interpretation. [Setup](setup.md) and the
[runbook](runbook.md) explain project-local operation and exact cleanup.

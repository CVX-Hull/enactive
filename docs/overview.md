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

The [architecture diagram](architecture.md#scope-and-responsibilities) answers “Who
decides, who sends input and who can stop it?” Its boxes are responsibilities, not
separate required models. The player interprets pixels; the
custodian serializes basic actions through the SDL adapter; the game determines
effects. The user can Pause independently. Memory contains fallible player claims
and never grants custody.

Each finite run freezes one [player host](components/player-interface.md) adapter
behind the substitutable [`player-host/3` contract](contracts/player-host.md). The selected
finite configuration is OpenRouter / explicitly pinned provider / DeepSeek Flash1017 at medium
effort. Its exact route, metadata, context and limits are frozen per run; this
selection is not a claim of model quality or provider performance.

The player keeps an ongoing user objective. Finite tests retain their quotas,
ending reserves and final-actor policy outside its supplied context. A separate
control channel can offer bounded finish-up; direct `player_finish` reports the
player's disposition. User Pause, hard limits and owned cleanup stop automation
independently of a model reply, saving or Quit. Saving remains an ordinary game
action, and stopping automation certifies neither persistence nor a paused game.
The [host contract](contracts/player-host.md#external-control) owns this current
source behavior; real-play qualification is a separate claim.

No candidate model or context change investigated so far has been adopted; the
[acceptance index](acceptance/index.md) holds each investigation and its limits.
Successful serving does not qualify useful cadence, and the player stays
self-sufficient: the lead gives no gameplay hints.

The [architecture](architecture.md) explains ownership, the
[player guide](player-guide.md) supplies compact working context, and the
[computer-control contract](contracts/computer-control.md) owns exact interfaces.

## What works and what the evidence means

| Boundary | Current scope and limit |
| --- | --- |
| Mechanical control | Actual CDDA key/text/pointer effects, useful stock, deliberate Save/new-child reload and separate normal exit are documented in the [production evidence](acceptance/2026-10-29-computer-control.md). Original uncertain exit ACKs remain unknown. |
| Player services | Actual image-conditioned scouting, failed/revised programs, source-backed correction and successor application are demonstrated. This is functional utility, not a safe-navigation or learning-benefit guarantee. |
| Player context | The [player guide](player-guide.md#play-from-observed-effects) works from observed effects. The player's spatial and search claims can exceed the evidence. No causal prompt benefit or general reliability is qualified. |
| Actor replacement | Actual old host/MCP quiescence and immutable context preceded a fresh successor under original limits. No game menu, save or identity condition grants authority. |
| Spectator | The [spectator](components/observer-operations.md) separates a supervised control path (frame, attention checks, Pause with a recorded reason) from a read-only viewer of the [run evaluator](contracts/evaluation.md). It shows whether anything warrants a Pause, drills from every number to its instances, and tracks changes, failure modes and cross-run comparisons with provenance on every value. Reader accuracy is validated on held-out frames, plus hand-checked night and day-rollover frames. No held-out clock falls between 7:50 PM and 6:00 AM, popup-covered clocks and severe need labels have no held-out examples, and creature counting and death recall are not yet validated ([reader validation](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383)). Human-usability efficacy remains unqualified. |
| Day-scale play | Screened on one diagnostic route rather than the selected configuration ([long-horizon arm](acceptance/2026-11-07-long-horizon-382.md)), not qualified; seven-day survival and cadence remain open. |
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
[#164](https://github.com/CVX-Hull/enactive/issues/164),
[#177](https://github.com/CVX-Hull/enactive/issues/177) and
[#145](https://github.com/CVX-Hull/enactive/issues/145) own cadence, learning and
independent survival outcomes, which the boundary does not imply.

Development runs use a diagnostic route that confers no player selection, under the
[development-run method](development-runs.md). The [run evaluator and
spectator](decisions/008-evaluation-and-spectator.md) score runs from recorded frames and
traces; whole-run survival cannot separate arms at affordable run counts, so each change
pre-registers a targeted process metric. Each run's result is in its dated record
([acceptance index](acceptance/index.md)).

#145's seven-day gate remains the north star, and #164's cadence criteria remain unqualified.

## How you stay in control of the project

Use the [Project](https://github.com/users/CVX-Hull/projects/2) for priorities,
[work](work.md) for evidence, and the [documentation map](documentation.md) for
review. The lead owns design, integration and verification; the deciding player
owns routine tactics and interpretation. [Setup](setup.md) and the
[runbook](runbook.md) explain project-local operation and exact cleanup.

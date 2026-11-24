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
The [glossary](glossary.md) defines the project's terms.

The current source uses a basic computer-control boundary. The harness provides
actual PNGs, mechanical window geometry, key/text/pointer/wait, exact operation
collection, one writer and original limits. It contains no game-phase, menu,
activity, item or character-identity eligibility checks. The playing system owns
all interpretation, save/load choices, plans, quantities, Work and success claims.
Curated knowledge and fallible player hints support continuity; ordinary input
remains available when a hint fails and mechanical custody is healthy.

The player does not maintain its own long-term memory. A separate
[curator](components/curator.md) reads what happened, publishes cited facts and articles
through a gate, and holds no custody. It can work beside play without making the player
wait, and between runs. Each fact (`curator-fact/5`) carries an open scope map and
typed links, so world-bound and context-scoped knowledge is delivered only to matching runs.

## How it works

The [architecture diagram](architecture.md#scope-and-responsibilities) answers “Who
decides, who can stop input and how does curated knowledge reach the player?” Its boxes
are responsibilities, not separate required models. The player interprets pixels; the
custodian serializes basic actions through the SDL adapter; the game determines
effects. The user can Pause independently. Curated knowledge and hints never grant custody.

Each finite run freezes one [player host](components/player-interface.md) adapter
behind the substitutable [player host contract](contracts/player-host.md). The selected
route, model and effort are in [player host activation](operations/player-host.md); the
exact route, metadata, context and limits are frozen per run, and the selection is not a
claim of model quality or provider performance.

The player keeps an ongoing user objective. Finite tests retain their quotas,
ending reserves and final-actor policy outside its supplied context. A separate
control channel can offer bounded finish-up; direct `player_finish` reports the
player's disposition. User Pause, hard limits and owned cleanup stop automation
independently of a model reply, saving or Quit. Saving remains an ordinary game
action, and stopping automation certifies neither persistence nor a paused game.
The [host contract](contracts/player-host.md#external-control) owns this current
source behavior; real-play qualification is a separate claim.

Knowledge moves beside play in four steps, each optional for a run:

1. **Curate.** A run launched with `--curator-runner` has a
   [curator runner](components/curator.md#runner-windows) that takes bounded snapshots of
   the live write-ahead-log store and runs sandboxed sessions over windows of finished
   steps. Its failure or lag never stops play.
2. **Deliver.** With [`live_knowledge_updates`](operations/campaign-run.md#live-knowledge-updates),
   on each poll the driver adopts the highest newer confirmed version it can verify and
   publish for the application and any successor. Between requests, the running host
   delivers the newest verified update that fits within context capacity as one message
   (refusing an oversized one for context capacity), while a successor starts from the
   driver's latest adopted version. Otherwise every actor keeps the package's frozen
   version.
3. **Cut.** The `player-host/11` route can enable `context_cut`. The host then replaces
   older turns with a fresh briefing, and only turns that the curator's confirmed,
   [unbroken coverage](contracts/player-host.md#coverage-gated-context-cut) has reached.
   Without that coverage, play continues with image eviction and handoff.
4. **Groom.** After a run is sealed, the operator can run
   [boundary grooming](operations/curator-hosts.md#post-admission-boundary-grooming) to
   merge, retire and reorganize the whole store for a later package.

No cheaper player model is adopted; the
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
| Player services | Curated knowledge is delivered to the player, at the start of an actor and during play, and hints are retained for curation. Benefit and safe-navigation guarantees are unclaimed. Player-authored programs are retired. |
| Player context | The [player guide](player-guide.md#play-from-observed-effects) works from observed effects. The player's spatial and search claims can exceed the evidence. No causal prompt benefit or general reliability is qualified. The host can cut turns the curator has covered; that source behavior is tested offline and not in real play. |
| Actor replacement | Actual old host/MCP quiescence and immutable context preceded a fresh successor under original limits. No game menu, save or identity condition grants authority. A successor starting from a version adopted during play is tested offline and not in real play. |
| Spectator | The [spectator](components/spectator.md) separates a supervised control path (frame, status, Pause with a recorded reason) from a read-only viewer of the [run evaluator](contracts/evaluation-record.md) and the curator runner's status. It shows whether anything warrants a Pause, drills from every number to its instances, and tracks changes, failure modes and cross-run comparisons with provenance on every value. Reader accuracy is validated on held-out frames, with gaps in night clocks, popups, need labels, creature counting and death recall ([reader validation](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383)). Human-usability efficacy remains unqualified. |
| Not yet qualified | Useful apparent cadence, causal learning benefit, independent seven-day survival, second-game control, broader geometry, Unicode/IME and actual-human takeover are not qualified. |

### Qualification and evidence matrix

Each row names the records that own its numbers and limits. “Live-verified” means it was observed in real play. “Offline or stand-in” means tests, replays or a
synthetic run. “No confirmed effect” means a study looked for a benefit and did not
confirm one. “Unqualified” means the evidence does not establish the outcome, or the
question is parked.

| Subject and evidence | Standing | What it shows | What it does not show |
| --- | --- | --- | --- |
| Day-scale play: [long-horizon arm (#382)](acceptance/2026-11-07-long-horizon-382.md) and [seven-day development lineage (#397)](acceptance/2026-11-07-seven-day-397.md) | Unqualified | Chained save/reload play past one in-game day. The #397 survivor passed its day 1 check and died on day 2. | Seven-day survival or useful cadence. |
| Benefit of delivered memory: [withholding study (#651)](acceptance/2026-11-14-withholding-study.md) | No confirmed effect | Delivered facts are used: the player acted in line with a delivered lead in most windows where it applied. | A benefit. The frozen primary is not positive, and harm was not tested. |
| A stated earlier sighting: [paired trunk replay (#829)](acceptance/2026-11-20-malvern-trunk-paired-replay-829.md) | Offline or stand-in | One supplied sentence moved every proposal to checking the trunk, at both context sizes. | That the check was the better move, or any effect in play. |
| Live curation: [first live curator run (#859)](acceptance/2026-11-21-live-curator-run-859.md) | Live-verified, partial | Every live snapshot read succeeded, and the published windows kept the backlog from growing. | A full admission: a gate defect stopped publication, and play ended early. |
| Live delivery, world and game scope, and boundary grooming: [live validation run (#889)](acceptance/2026-11-22-live-validation-run-889.md) | Live-verified, one actor | Every examined window was published and delivered during play, world facts stayed out of articles, and one grooming session reorganized the store. | Actor handoff, or that delivery improved play. |
| Curation across an actor handoff: [stand-in run (#851)](acceptance/2026-11-20-live-curator-stand-in-run-851.md), with host and driver tests | Offline or stand-in | Beside a synthetic writer, the runner examined an ended actor's tail before its successor's steps. Tests cover the successor's starting version. | A handoff in real play with the runner. |
| Coverage-gated context cut: [decision brief (#890)](acceptance/2026-11-22-context-cut-decision-brief-890.md) and its [implementation (#900)](https://github.com/CVX-Hull/enactive/issues/900) | Offline or stand-in | Replaying #889's schedule projects smaller prompts and lower cost; the host behavior is tested. | Any real cut in play, its cost or its effect on the player's task. |

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
The [acceptance index](acceptance/index.md) lists the evidence; GitHub owns execution
and remaining gates.

## Current direction and decisions

[ADR006](decisions/006-computer-control-boundary.md) explains the selected boundary;
[#164](https://github.com/CVX-Hull/enactive/issues/164),
[#445](https://github.com/CVX-Hull/enactive/issues/445) and
[#145](https://github.com/CVX-Hull/enactive/issues/145) own cadence, curated memory and
programs, and independent survival outcomes, which the boundary does not imply.

Each development run freezes its route and configuration; the
[development-run method](development-runs.md) says how comparisons are measured and
recorded. The [run evaluator](contracts/evaluation-record.md) scores runs from recorded frames
and traces, and the [spectator](components/spectator.md) presents them.

## How you stay in control of the project

Use the [Project](https://github.com/users/CVX-Hull/projects/2) for priorities and open
work, the [acceptance index](acceptance/index.md) for evidence, and the [documentation map](documentation.md) for
review. The lead owns design, integration and verification; the deciding player
owns routine tactics and interpretation. [Setup](setup.md) and the
[runbook](runbook.md) explain project-local operation and exact cleanup.

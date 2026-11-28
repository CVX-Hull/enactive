---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Project overview

## What we are building

Enactive lets a designated agent play CDDA-class survival/roguelike games from
visible computer observations while a user watches and can stop automation. The
[charter](charter.md) owns purpose, the continuous long-horizon play target (with
operator-initiated pause and resume carrying over game knowledge and prior goals)
and the non-blocking latency constraints. Today, Pause permanently fences automation
for the running admission ([pause and timeout](operations/pause-timeout.md)), while
`player_agenda` carryover across cuts, handoffs and resumed admissions is implemented
in `player-host/13` (`player-agenda-continuation/1`, verified offline;
[player working-state agenda](decisions/owner-decisions.md#player-working-state-agenda-1026);
operator-initiated Pause/Resume continuation remains in
[#1057](https://github.com/CVX-Hull/enactive/issues/1057)). CDDA is the first actual
target; no second game or unattended survival service is qualified.
The [glossary](glossary.md) defines the project's terms.

The current source uses a basic computer-control boundary. The harness provides
actual PNGs, mechanical window geometry, key/text/pointer/wait, exact operation
collection, one writer and original limits. It contains no game-phase, menu,
activity, item or character-identity eligibility checks. The playing system owns
all interpretation, save/load choices, plans, quantities, Work and success claims.
Curated knowledge and fallible player hints support continuity; ordinary input
remains available when a hint fails and mechanical custody is healthy.

A separate [curator](components/curator.md) is the sole writer of durable long-term
memory: it reads what happened, publishes cited facts and articles through a gate,
and holds no custody. It works beside play without making the player wait, and
between runs. Each fact (`curator-fact/6`) carries an open scope map, a closed five-value
`statement_kind` (Kinds 1–5 only, with no recommendations or plans), optional `state_key`,
kinematic `anchor`, grounded `when`, `depiction_source_id` and typed links, so world-bound
and context-scoped knowledge is delivered only to matching runs. Player-owned ephemeral
working state and self-directed goals stay separate from curated memory in the host-local
`player_agenda` tool (`player-agenda-continuation/1`), which carries across cuts, handoffs
and resumed admissions and never enters curator snapshots or traces.

## How it works

The [architecture diagram](architecture.md#scope-and-responsibilities) answers “Who
decides, who can stop input and how does curated knowledge reach the player?” Its boxes
are responsibilities, not separate required models. The player interprets pixels; the
custodian serializes basic actions through the SDL adapter; the game determines
effects. The user can Pause independently. Curated knowledge and hints never grant custody.

Each finite test admission freezes one [player host](components/player-interface.md) adapter
behind the substitutable [player host contract](contracts/player-host.md); finite
admissions are bounded evaluation and budget slices rather than the product's
intended play interruptions ([decision](decisions/owner-decisions.md#continuous-long-horizon-play-and-broader-pace-scope)). The selected
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
3. **Cut.** The `player-host/13` route can enable `context_cut`. The host then replaces
   older turns with a fresh deterministic briefing (zero background LLM recall) and a cut
   marker carrying `recent_intents`, removed `source_ids`, a bounded substantive
   `changes_since` delta, `uncovered_turns` and committed `player_agenda` threads,
   preferring turns that the curator's confirmed
   [unbroken coverage](contracts/player-host.md#coverage-gated-context-cut) has reached.
   Under sustained curator lag above the secondary pressure ceiling or on hard-capacity
   rescue, the host applies a bounded deterministic uncovered-cut fallback without advancing
   `covered_through_operation_id` and while keeping disk WAL ingestion unchanged
   ([#1037](https://github.com/CVX-Hull/enactive/issues/1037)).
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
| Player context | The [player guide](player-guide.md#play-from-observed-effects) works from observed effects. The player's spatial and search claims can exceed the evidence. No causal prompt benefit or general reliability is qualified. Live coverage-gated context cuts ran in the [seven-day campaign (#896)](acceptance/2026-11-22-seven-day-campaign-896.md) on `player-host/11`; causal benefit on task outcome remains unqualified. |
| Actor replacement | Actual old host/MCP quiescence and immutable context preceded a fresh successor under original limits. No game menu, save or identity condition grants authority. Real-play actor handoffs alongside the live curator ran in the [seven-day campaign (#896)](acceptance/2026-11-22-seven-day-campaign-896.md) (`A4`, `A9`). |
| Spectator | The [spectator](components/spectator.md) separates a supervised control path (frame, status, Pause with a recorded reason) from a read-only viewer of the [run evaluator](contracts/evaluation-record.md) and the curator runner's status (`spectator-view/3`). It shows whether anything warrants a Pause, drills from every number to its instances, and tracks changes, failure modes and cross-run comparisons with provenance on every value. Reader accuracy is validated on held-out frames, with gaps in night clocks, popups, need labels, creature counting and death recall ([reader validation](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383)). Human-usability efficacy remains unqualified. |
| Not yet qualified | Useful apparent cadence, causal learning benefit, general or default-stat seven-day survival beyond the single custom-character [#896](acceptance/2026-11-22-seven-day-campaign-896.md) lineage, fresh-world live validation and a multi-actor live handoff on `curator-knowledge/5` / `delivered-knowledge/4` / `player-host/13`, multi-day standard-build survival beyond the single [three-day lineage (#998)](acceptance/2026-11-26-multi-day-standard-build-campaign-998.md), a live `spend-reserve-reached` handshake, second-game control, broader geometry, Unicode/IME and actual-human takeover are not qualified. |

### Qualification and evidence matrix

Each row names the records that own its numbers and limits. “Live-verified” means it was observed in real play. “Offline or stand-in” means tests, replays or a
synthetic run. “No confirmed effect” means a study looked for a benefit and did not
confirm one. “Unqualified” means the evidence does not establish the outcome, or the
question is parked.

| Subject and evidence | Standing | What it shows | What it does not show |
| --- | --- | --- | --- |
| Seven-day survival campaign: [seven-day campaign (#896)](acceptance/2026-11-22-seven-day-campaign-896.md) | Live-verified, single lineage | Autonomous survival past seven full in-game days (`168 h 24 m 07 s`, `606,247` s) across 10 supervised admissions (`campground-seven-day-896-b`) on `campaign-run/12`, `player-host/11`, and `curator-knowledge/3`, with `86/86` settled live curator sessions (`v0`→`v91`) and `0` manual inputs. | Default-stat or multi-seed survival (custom `12/12/12/12` `overpowered` Survivor) or causal benefit of delivered memory (unablated). |
| Earlier day-scale play: [long-horizon arm (#382)](acceptance/2026-11-07-long-horizon-382.md) and [seven-day development lineage (#397)](acceptance/2026-11-07-seven-day-397.md) | Unqualified | Chained save/reload play past one in-game day. The #397 survivor passed its day 1 check and died on day 2. | Seven-day survival or useful cadence. |
| Benefit of delivered memory: [withholding study (#651)](acceptance/2026-11-14-withholding-study.md) | No confirmed effect | Delivered facts are used: the player acted in line with a delivered lead in most windows where it applied. | A benefit. The frozen primary is not positive, and harm was not tested. |
| A stated earlier sighting: [paired trunk replay (#829)](acceptance/2026-11-20-malvern-trunk-paired-replay-829.md) | Offline or stand-in | One supplied sentence moved every proposal to checking the trunk, at both context sizes. | That the check was the better move, or any effect in play. |
| Live curation: [first live curator run (#859)](acceptance/2026-11-21-live-curator-run-859.md) | Live-verified, partial | Every live snapshot read succeeded, and the published windows kept the backlog from growing. | A full admission: a gate defect stopped publication, and play ended early. |
| Live delivery, world and game scope, and boundary grooming: [live validation run (#889)](acceptance/2026-11-22-live-validation-run-889.md) | Live-verified, one actor | Every examined window was published and delivered during play, world facts stayed out of articles, and one grooming session reorganized the store. | Actor handoff, or that delivery improved play. |
| Curation across an actor handoff: [seven-day campaign (#896)](acceptance/2026-11-22-seven-day-campaign-896.md) (`A4`, `A9`), [stand-in run (#851)](acceptance/2026-11-20-live-curator-stand-in-run-851.md), and host/driver tests | Live-verified on `curator-knowledge/3` | Beside play on `campaign-run/12` + `curator-knowledge/3`, actor handoffs (`001`→`002`) ran alongside the live curator runner; stand-in and tests cover ended-actor tails and successor version adoption. | Causal benefit, or a live handoff on `curator-knowledge/5` / `delivered-knowledge/4` (prior [#963](acceptance/2026-11-25-wave3-wave4-live-validation-963.md) and [#998](acceptance/2026-11-26-multi-day-standard-build-campaign-998.md) runs each used one actor per admission). |
| Coverage-gated context cut: [seven-day campaign (#896)](acceptance/2026-11-22-seven-day-campaign-896.md), [decision brief (#890)](acceptance/2026-11-22-context-cut-decision-brief-890.md) and [#900](https://github.com/CVX-Hull/enactive/issues/900) | Live-verified, unablated | Executed `77` live cuts (`2,128` held-back checks) across 10 admissions in `#896-b` with `92.27%` prompt cache share; offline replay projects lower prompt cost. | Paired with/without cut comparison or causal effect on survival. |
| Scoped knowledge graph & ranking (`curator-knowledge/4`, `delivered-knowledge/3`, `campaign-run/13`, `spectator-view/3`): [retrieval baseline (#936)](acceptance/2026-11-24-wave3-retrieval-baseline-and-curator-recount-936.md), [#937](https://github.com/CVX-Hull/enactive/issues/937) and [bounded live validation (#963)](acceptance/2026-11-25-wave3-wave4-live-validation-963.md) | Live-verified, one actor, bounded | `#936`/`#937` cover ranking and fixtures offline. `#963` played one unmodified `8/8/8/8` Survivor (Rowan Reed, `Doering`) on standard rules: `27/27` live curator windows (`v1`–`v29`) accepted, grooming `v29`→`v30` with `stale_records: 0`, and `151` active facts and `9` active articles (`4` world-scoped), all with `scope.ruleset == "standard"`; operator-observed `spectator-view/3` probes answered. | A multi-actor live handoff on this store, a multi-day standard-build campaign, populated draft containers in live play, or a benefit of delivered memory. |
| Player runtime, recall dedup, hysteresis cuts & compact queries (`player-host/12`, `player-knowledge/3`): [Porter2 and replay gates (#949)](acceptance/2026-11-25-player-host-12-porter2-and-replay-gates-949.md), [#950](https://github.com/CVX-Hull/enactive/issues/950) and [bounded live validation (#963)](acceptance/2026-11-25-wave3-wave4-live-validation-963.md) | Live-verified, one actor, bounded | `#949` replay and `#950` tests verify the design offline. In `#963`, `797` player and `60` recall requests ran at `94.04%` cache read share, `4%` large rewrites and `$0.0051` per decision, with `26` context cuts and `0` hard capacity stops, `69` reminder checks with `0` `already_in_context` overlap, and `16` compact `player-knowledge/3` queries; play ended on an orderly `host_seconds` stop with `normal_native_exit_zero: true`. | A live `spend-reserve-reached` handshake (`0` events), a multi-actor handoff, multi-day play, or a causal benefit of cuts or recall. |
| Multi-day standard-build campaign (`campaign-run/13`, `curator-knowledge/4`, `delivered-knowledge/3`, `player-host/12`): [three-day campaign (#998)](acceptance/2026-11-26-multi-day-standard-build-campaign-998.md) | Live-verified, single lineage | The [owner](decisions/owner-decisions-archive.md#multi-day-campaign-accepted-reserve-stop-waived-998) accepted it for the player-owned campaign outcome with the reserve-stop item waived. One unmodified `8/8/8/8` survivor reached a saved clock 72 h 2 min 48 s past the start in four admissions for `$35.45`, each ending with a save, a separate quit and a zero native exit. The knowledge chain is unbroken from v0 to v101, and in later admissions the player read and acted on records from earlier ones. All 2,201 game inputs match a hosted actor's tool call. | A stop on the dollar reserve (the advisory spend notice ended three admissions first), an actor handoff, a sustainable food supply, a second lineage, or a causal benefit of memory. |
| Keyed fluents, anchors, clocks, Kinds 1–5 & hygiene (`curator-knowledge/5`, `curator-fact/6`, `curator-submission/3`, `delivered-knowledge/4`, `player-knowledge/4`): [store-migration contract](design/store-migration-contract.md), [freeze/baselines (#1046)](acceptance/2026-11-27-store-migration-freeze-and-998-baselines-1046.md) and [Batch 1 checks](acceptance/2026-11-27-batch1-store-migration-checks.md) | Offline or stand-in | Gate invariants, exporter, reader, deterministic hygiene worklist, spectator projections, paired retrieval replay adopting query-matched claim snippets (`4/4` `#998` snippet pass, zero regression on `#896-b`/`#889`), and standing `C-MODEL-CHECK` (`3/3` publications `v0`→`v3`, `$0.3909`) pass with zero compatibility shims. | Fresh-world live validation on `curator-knowledge/5`, a multi-actor live handoff, or a causal benefit in play. |
| Player working-state agenda, substantive deltas, retired recall & same-lineage ancestor source index (`campaign-run/14`, `player-host/13`, `player-host-inputs/5`, `player-source-index/1`, `player-source-read/2`, `player-agenda-continuation/1`): [Batch 2 checks (#1025, #1026)](acceptance/2026-11-27-batch2-player-continuity-checks.md) | Offline or stand-in | Host-local `player_agenda` carryover across cuts/handoffs/resumes with zero curator leakage, bounded claim-level substantive deltas (`0` empty updates on `#998` replay), deterministic `bm25_1hop` overflow briefing, zero LLM recall, same-lineage ancestor `player_source` reads (`785/785` `#998 v94` frames), 5-session `#963`+`#998` archive cutover, and pre-merge `C-MODEL-CHECK` pass offline. | Fresh-world live validation on `campaign-run/14` / `player-host/13`, multi-actor live handoff, or causal benefit in play. |
| Tiered uncovered-cut fallback (`player-host/13`): [lag replay (#1037)](acceptance/2026-11-27-uncovered-cut-lag-replay-1037.md) | Offline or stand-in | On `#998` replay (`2,504` requests), Tiered `100k` matches baseline on recorded `default` tier (`0` uncovered cuts), cuts mean prompt tokens by `-34.5%` under heavy `flex` + `15m` `429` burst, eliminates all `3/4` curator-stall stops, and retains `100%` of dropped frames in `source_ids` without advancing `covered_prefix`. | Live gameplay quality when unsynthesized turns leave the prompt before publication, or real provider `flex` queue latency. |
| Non-real-time curation cost levers, `40/60` cadence & `flex` probe (`curator-host/2`, `curator-runner-config/2`): [cadence replay (#1027)](acceptance/2026-11-27-curation-cost-cadence-1027.md) and [flex probe (#1047)](acceptance/2026-11-27-flex-tier-probe-1047.md) | Offline replay & bounded probe | `#1027` replay shows `40/60` cadence cuts windows by `20.7%–48.2%` across lag regimes with `0/4` stops; `#1047`'s 2-window sealed `#998` probe verified `20/20` applied `flex` responses, exact `0.5000×` billing (`$0.0938`, `-77.9%` vs. `#998` baseline), `0` `429`s, `18/20` prefix-suffix reservations, and `2/2` clean `curator-knowledge/5` publications. | `flex` contention, queue wait and `429` frequency across multi-admission live play, `40–60`-step windows, long-prompt (`>= 272k`) `flex` pricing, or live interleaved hygiene passes. |

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
[#136](https://github.com/CVX-Hull/enactive/issues/136) own cadence, curated memory and
programs, and independent survival campaigns, which the boundary does not imply.

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

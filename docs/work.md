---
owner: lead
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Work and evidence navigation

The [public Project](https://github.com/users/CVX-Hull/projects/2) and GitHub Issues
own live execution. This page routes to scoped evidence; it is not a second backlog.
[Overview](overview.md) owns capabilities and limits.

## Development loop and long-horizon arm

The [development-run method](development-runs.md) owns the benchmark, metric and
classification; each study's decisions and results are in its dated record, and
per-run quantities are in the tracked run ledger.
[#145](https://github.com/CVX-Hull/enactive/issues/145)'s seven-day gate is the north
star; [#164](https://github.com/CVX-Hull/enactive/issues/164)'s cadence criteria wait
for a capability baseline.

- **Development loop, 6 November 2026** ([#372](https://github.com/CVX-Hull/enactive/issues/372),
  [record](acceptance/2026-11-06-development-loop.md)): ceiling median 0.59 in-game
  hours within a 250-decision allowance; three grounding aids rejected (zoom had no
  uptake; the aids did not isolate perception); survival was bounded by time scale.
- **Evaluation framework, 7 November 2026** ([#383](https://github.com/CVX-Hull/enactive/issues/383),
  [ADR008](decisions/008-evaluation-and-spectator.md),
  [record](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383)):
  the evaluator re-scored the loop and the spectator views it; changes pre-register targeted process
  metrics, with survival, cost and setup as guards.
- **Long-horizon arm, 7 November 2026** ([#382](https://github.com/CVX-Hull/enactive/issues/382),
  [record](acceptance/2026-11-07-long-horizon-382.md)): two of three save/reload
  lineages Day-viable, a screen; lineage 3 ended on an input-window stall
  ([#396](https://github.com/CVX-Hull/enactive/issues/396)).

Deferred by ADR008 until after #382: intent visibility
([#384](https://github.com/CVX-Hull/enactive/issues/384)), label writing
([#385](https://github.com/CVX-Hull/enactive/issues/385)), judges
([#386](https://github.com/CVX-Hull/enactive/issues/386)), a cross-run channel
([#387](https://github.com/CVX-Hull/enactive/issues/387)) and a scenario bank
([#388](https://github.com/CVX-Hull/enactive/issues/388)). The seven-day attempt and
its cost and latency plan are [#397](https://github.com/CVX-Hull/enactive/issues/397).

## Current integrated checkpoint

The production source has the [computer-control boundary](contracts/computer-control.md):
basic pixels/input, mechanical custody/resources, independent permanent Pause,
optional player-owned memory/program/context and actor-only handoff.
[#176](https://github.com/CVX-Hull/enactive/issues/176) delivered it on 29 October 2026,
with [#287](https://github.com/CVX-Hull/enactive/issues/287) and
[#288](https://github.com/CVX-Hull/enactive/issues/288) for its mechanical and
playing-system responsibilities. [ADR006](decisions/006-computer-control-boundary.md)
and the [cutover brief](changes/071-computer-control-cutover.md) retain rationale.

The [production evidence](acceptance/2026-10-29-computer-control.md) consolidates
actual pointer/text effects, useful stock, image-conditioned scouting, correction,
fresh succession, deliberate Save/new-child reload and final normal ending.
The [development record](acceptance/2026-10-29-computer-control-development.md)
preserves intermediate failures. Protected PR/main delivery receipts are in #176
and its linked PR; this page does not duplicate the tracker.
Each finite package freezes one player host adapter under the
[player host contract](contracts/player-host.md); each OpenRouter / DeepSeek Flash1017
medium package pins its provider. The [recorded endpoint dispositions](acceptance/2026-10-29-computer-control.md#failures-and-endpoint-disposition)
are not a quality ranking. The current player host retries one transient provider
failure per logical request ([#308](https://github.com/CVX-Hull/enactive/issues/308);
429, 502/503/504, a pre-header fetch rejection or OpenRouter's in-flight 402), proven
by offline fixtures only; no live 5xx has yet exercised it.

The host evicts historical screenshots in whole count-only blocks of each package's
frozen `context_image_block`, so the prompt prefix stays cacheable between evictions
(the development runs used peak 39, block 10). A bounded live check on Gemini/Vertex
proved the mechanism only and narrowly failed its pre-set cost rule (0.52× against
≤ 0.5×); its cost, provenance and the owner's disposition are on
[#313](https://github.com/CVX-Hull/enactive/issues/313). Play behaviour with up to
39 frames, residency at game pace and other providers remain unmeasured.

The compact [player guide](player-guide.md#play-from-observed-effects) now emphasizes
observed effects, quantity/container scope and confirmation focus. The
[player-context study](acceptance/2026-10-29-player-context.md) retains its authentic
baseline, useful care/food progression, fresh-child quantity reconciliation and
unsuccessful continuations. #280 owns its source-delivery receipts; the study does
not qualify parent cadence, learning or survival.

## Decisive evidence

The agreed [player-objective and external-test-control rationale](changes/073-player-objective-and-test-control.md)
links the context audit to [#359](https://github.com/CVX-Hull/enactive/issues/359).
[PR #360](https://github.com/CVX-Hull/enactive/pull/360) delivered `player-host/3`,
projected actor results and `player-memory/2` on main:
this is source delivery, not a cohort qualification. The scoped
[ongoing-objective diagnostic](acceptance/2026-11-05-player-test-diagnostic.md) and
[recorded-screen candidate assessment](acceptance/2026-11-05-recorded-player-assessment.md)
below qualify no player; current player selection and all qualification gates are
unchanged. The owning issues (#359, #164, #145) record the remaining real-use paths,
live gates and execution.

| Evidence | Scope and limitation |
| --- | --- |
| [Standards and discoverability audit](acceptance/2026-11-07-standards-audit.md) (#400) | Eight-lens audit of docs, code, tests, controls and tracker at `bd549ca`: no ADR006 boundary violation; drift fixed in #406 and #407. Every remaining finding was closed in #412, #413 and #415–#419, kept with a reason, or deferred with a trigger. Its new findings are closed: diagram determinism #414 (#427), unindexed evidence #420 (#424, #426) and check-log capture #421 (#428). Follow-up #425 retired the remaining old `.runtime` run output on the owner's decision ([record](acceptance/2026-11-07-runtime-retirement.md), #429) and removed legacy narrative from current docs (#430). |
| [Long-horizon arm](acceptance/2026-11-07-long-horizon-382.md) (#382) | GPT-6.1 Terra (a diagnostic route) in chained save/reload admissions: two of three lineages passed a hand-checked 24 h day check. A screen on three lineages, not a qualification; one lineage ended on an input-window stall (#396). |
| [Evaluator re-score and power check](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383) (#383) | The ADR008 evaluator re-scored all 30 loop runs, with stated differences from the hand tables; its readers were validated on held-out frames with stated gaps. Whole-run survival cannot separate arms at affordable n. |
| [Development loop](acceptance/2026-11-06-development-loop.md) (#372) | Ceiling median 0.59 in-game hours in a 250-decision allowance; three grounding aids rejected (two on that metric, zoom for no uptake). Survival there was bounded by time scale, not isolated as perception. |
| [Recorded-screen candidate assessment](acceptance/2026-11-05-recorded-player-assessment.md) | Four requests through the unchanged host; both cases narrowly promising, no executed effects. The retreat key opens a movement-mode menu, with Run selection untested. No model ranking, program, survival or cadence qualification. |
| [Ongoing objective under finite test control](acceptance/2026-11-05-player-test-diagnostic.md) | Two admissions: first missed operator watch deadline; replacement maintained coverage, acquired a dog whistle, then Alex died. Direct finish/context separation worked; no food/water gain, program, external finish-up, persistence or cadence qualification. |
| [Player context and testing responsibilities](acceptance/2026-11-05-player-context-audit.md) | Audits the then-main player's complete context construction and retained Alex assignment. Maps experiment quotas and finish-line instructions across prompts, tools and program views; rationale for #359, not evidence that its candidate is accepted. |
| [ADR-007 first-slice outcome](acceptance/2026-11-03-adr007-status-quo.md) | The owner retained the current player after the offline feasibility screen. V4 benefit remains unestablished. |
| [Transition corpus](acceptance/2026-11-01-transition-corpus.md) | Method calibration under a reviewed pre-registration; one procedural deviation, accepted by the owner (resumed after a provider failure before consulting the owner; runs 02–10). 37 complete runs of the unchanged #314 arm-A player from one restored state; 2,605 transitions labelled with frozen alphabets A1 and A2. On A1, at disagreement 3.1% [1.6–6.0%]: the action predicts the next state (0.354 bit held-out; predictive, not interventional); no two-set slow split with τ ≥ 40 (τ = 20 not excluded); memory beyond one step indeterminate (d exceeds the 1.9% gate). A2 descriptive only. One start state, one policy, no terminal events. |
| [Grounded no-gain diagnosis](acceptance/2026-10-31-grounded-no-gain-diagnosis.md) | Diagnostic only, with blind audit and restored state. Gemini ×3 (one run with a 300-attempt budget) and Haiku ×1 all made no retained change from one shared save. C ended by choice at 95/300, consistent with budget not being the bottleneck; H matched A, consistent with the pattern not being model-specific (n = 1 each). Goal selection versus control was not separated: no nudge arm, per the owner. Gemini reports overstated, but they followed the included predecessor report as a template. |
| [Capable-player qualification](acceptance/2026-10-31-capable-player.md) | Three models conformed under `player-host/1`; Gemini led a fixed visual check, then grounded and navigated with one normal ending but no readiness gain and an inflated report; rejected. An account-credit 402 and a provider 503 ended two admissions. |
| [Visual-player qualification](acceptance/2026-10-30-visual-player.md) | Qwen/Wafer served substantive play and fresh Load with normal endings, but retained spatial/confirmation errors and no readiness gain; candidate rejected, earlier provider failures preserved. |
| [Spatial grounding and context rejection](acceptance/2026-10-30-spatial-grounding.md) | Primary-literature-informed candidate failed retained frame assessment and organic play; no retained readiness gain, guide restored, original failures/normal ending preserved. |
| [Observed effects and useful continuation](acceptance/2026-10-30-observed-effects.md) | Prospective unchanged-guide baseline/assessment: limited exploration and corrections, no retained readiness gain; no repair adopted; the later spatial study tests and rejects one candidate. |
| [Current and recorded investigation](acceptance/2026-10-30-spectator-investigation.md) | Automatic as-of Analysis, linked original intervals/program preparation, real Pause and separate persisted-water/normal-ending evidence; provider failure, player confirmation errors and usability limits remain. |
| [Watch and recent Timeline](acceptance/2026-10-29-spectator-watch-timeline.md) | Linked investigation and real same-page normal/Pause/fresh-admission control; failed beliefs, source-specific coverage and timing limits remain. |
| [Player context through actual play](acceptance/2026-10-29-player-context.md) | Fire clearance, new food actually used, saved-state continuity and a corrected water claim; remaining quantity/search/control errors and failed trade/rest are retained. |
| [Production computer control](acceptance/2026-10-29-computer-control.md) | Composite authentic useful play/program/knowledge/succession and Save/reload/normal ending; failed admissions remain failed. |
| [Basic computer-control proof](acceptance/2026-10-29-basic-computer-control.md) | Earlier isolated raw delivery/scouting evidence and failures; not production acceptance or CDDA pointer qualification. |
| [Organic corrected-program play](acceptance/2026-10-28-organic-play.md) | Useful exact correction by a fresh successor on the earlier semantic system, with normal ending and packaging/quantity limits. |
| [Endpoint comparison](acceptance/2026-10-28-endpoint-gameplay.md) | Faster serving and normal endings coexist with shallow progress and failed routines; useful cadence remains unqualified. |
| [Generic-host qualification](acceptance/2026-10-25-generic-host-qualification.md) | Retains actual source/route failures; mandatory host adoption is separate from model qualification. |
| [Supervised seven days](acceptance/2026-10-19-seven-day-survival.md) | Supervised trajectory, not independent seven-day acceptance. |
| [Independent supplies/shelter](acceptance/2026-10-21-independent-supply-shelter.md) | Bounded useful mission on earlier source; no general survival guarantee. |

The [acceptance directory](acceptance/) preserves intermediate failures, original
unknown acknowledgments, interventions and costs. Evidence stays bound to its
actual source/route/native bytes. Later repairs cannot change an earlier outcome.

## Campaign delivery path

[Development-first delivery](workflows/development.md#development-first-delivery)
and [risk-based assurance](workflows/review.md#risk-based-assurance) govern focused
feedback, independent review and protected acceptance. Broader cadence
[#164](https://github.com/CVX-Hull/enactive/issues/164), learning
[#177](https://github.com/CVX-Hull/enactive/issues/177), independent survival
[#145](https://github.com/CVX-Hull/enactive/issues/145) and portability
[#191](https://github.com/CVX-Hull/enactive/issues/191) remain separate claims.

## Retained evidence

Git owns source history. Original large artifacts/saves remain project-local under
ignored runtime paths and may be unavailable in a fresh checkout. Follow
[evidence retention](operations/evidence-cleanup.md#evidence-retention-and-cleanup)
and current [custodian closeout](operations/campaign-run.md#start-and-close).
Removing a failed world from a menu never erases its evidence.

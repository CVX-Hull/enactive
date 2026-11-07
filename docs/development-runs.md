---
owner: lead
review_trigger: A new development run, a change to the benchmark or metric, or a step-5 branch decision
status: active
---

# Development runs: ceiling benchmark and grounding aids

This page owns the benchmark, metric and one-row-per-run results of the current
development loop. Each run also gets one comment on its owning issue,
[#372](https://github.com/CVX-Hull/enactive/issues/372). Acceptance records and
independent review are reserved for adoption decisions, contract changes and
merges ([evidence cadence](workflows/evidence-cadence.md)).

## Owner decisions, 5 November 2026

| | Decision |
| --- | --- |
| D1 | Development runs use the supervisor's `best-effort` attention policy: Pause, uncertainty/custody stops, the independent custody deadline and finite limits stay; the 45-second lead acknowledgement does not apply ([supervision](operations/campaign-supervision.md)). No automated acknowledgements. |
| D2 | New model/gameplay spend for this loop is at most $150, keeping the cumulative actual upper bound at or below $410 within the standing $1,000. The lead admits runs inside it without per-run approval ([budget delegation](operator-permissions.md#finite-gameplay-budget-delegation)). |
| D3 | [#145](https://github.com/CVX-Hull/enactive/issues/145)'s fresh, unassisted seven-day survival is the north star. [#164](https://github.com/CVX-Hull/enactive/issues/164)'s cadence criteria (20 useful decisions, 2 s p95, 5 s stall, 500 ms local effect) are deferred until a capability baseline exists. They are not deleted or met. |
| D4 | One table row plus one issue comment per development run. |

## Question and decision rule

Can a frontier model survive in CDDA through the current pixels-and-keys boundary?
Earlier cheap-model results cannot answer this: the only multi-day survival
(19 October) used a frontier coding agent with a game-aware harness, and every
later run changed both the model class and the boundary.

Five ceiling runs of GPT-6.1 Terra decide the next branch, fixed before any run:

- **Median survival at least 24 in-game hours:** perception and control are
  adequate for a frontier model. Next is a cost and latency reduction plan
  (cheaper models, programs), and #164's design resumes.
- **Median below 24 in-game hours:** grounding is the bottleneck. Test the
  game-neutral, player-owned aids below against the ceiling arm.

A survivor still alive when its allowance ends counts at its observed hours, so
the rule asks whether the player survives 24 hours *within the allowance*. Using
time well (resting, waiting out the night) is part of the tested competence, not
a separate pacing effect. The run note states whether each survivor died, was
alive at stop, or stopped by its own choice, so a reader can see when pacing rather
than death decided the median.

An aid is adopted only when its arm's median survival exceeds the ceiling arm's
by at least 50% and at least 2 in-game hours, with no more setup failures than
the ceiling arm. Otherwise the change is reverted and the result recorded. With
five runs per arm this detects only large effects; it is a screen, not a
qualification.

## Benchmark

Every run starts from a fresh project-local userdir containing only normal
windowed input options: no world, save, player memory or predecessor report.
The previous run's userdir and game log are archived, never deleted. The player
creates a normal world with default rules and its own survivor through ordinary
visible menus, then pursues indefinite survival. The lead gives no class,
traits, location, tactic, target item or hint.

| Start | Assignment difference |
| --- | --- |
| S1 | The player uses the default **Evacuee** scenario; profession, traits and stats are its choice. |
| S2 | The player chooses every setup option, including the scenario. |

Runs alternate S1, S2, S1, S2, S1 within an arm. Each run is frozen as a fresh
`campaign-run/4` package from merged main, with these limits outside the
player's context:

| Setting | Value |
| --- | --- |
| Route | OpenRouter, `openai/gpt-6.1-terra`, pinned `openai`, no fallback, medium effort, default tier |
| Context | 262,144-token window, 16,384 output tokens, 32,768 reserve (successor handoff when reached); 39 images, evicted in blocks of 10 |
| Requests | 250 charged HTTP attempts including retries, across at most 2 hosts |
| Time | 7,200 host seconds; 7,800 custodian seconds |
| Supervision | `--attention best-effort` |

The window stays below OpenRouter's 272,000-token long-prompt threshold, so the
short-prompt rates apply: $1.00/M input, $1.25/M cache write, $0.05/M cache read
and $5.00/M output (read from the public model list on 5 November 2026). The
validator's worst case is (262,144 × $1.25 + 16,384 × $5.00) / 1M = $0.4096 per
attempt, or $102.40 per run. Costs are reconciled against OpenRouter's
per-generation records.

**Pilot (P1).** The first run used a 131,072-token window with 30 images evicted
one at a time. Context grew about 1.3k tokens per request, both hosts handed off
at the window's reserve and the run ended after 136 of its 250 attempts. Each
request also rewrote the prompt cache. The scored runs therefore use the larger
window, so the attempt allowance binds rather than context, and the block
eviction from [#313](https://github.com/CVX-Hull/enactive/issues/313), which keeps
the cached prefix stable between evictions. The pilot is retained but is not one
of the five scored ceiling runs.

**Current admission rule (from aid run B3).** Packages freeze the standing $1,000
as their `ceiling_usd` worst-case guard, and D2 is enforced on actual
provider-reported spend: a run is admitted only while actual new spend plus twice
the largest single run so far stays within $150 (owner decision, 6 November 2026;
[budget delegation](operator-permissions.md#finite-gameplay-budget-delegation)).
The pre-loop actual upper bound was $258.406176979 over 11,353 attempts, after #369.

**Earlier rule (P1 through B2).** Packages froze D2's lower limit, the pre-loop bound
plus $150 ($408.406176979; P1 and C1 used $410), as `ceiling_usd`, so a run was
admissible only while the remaining headroom covered its full $102.40 worst case,
that is, while cumulative actual spend stayed at or below $306.01. The rule
refused B3's package after $48.50 of actual new spend; that package never started.
The reservation is a worst case, not an invoice, and actual spend stayed far below
it.

## Metric

Measured by the lead from original frames and receipts; an independent reviewer
samples the claims in each arm.

- **Survival hours (primary):** in-game time from the first in-play clock to the
  last frame showing the survivor alive, or to the death screen.
- **Status:** died, alive at stop (attempt allowance, time or context capacity
  ended the run), or player finished. Dates are UTC.
- **Verified improvements:** distinct visible changes that improve needs (thirst,
  hunger, fatigue or pain reduced), supplies (new food, water or tools confirmed
  carried) or shelter (secured and used for rest). Claims without a confirming
  frame do not count.
- **Death cause**, if shown.
- **Cost:** dollars, charged attempts, setup attempts (until the first in-play
  frame) and wall seconds. The **$ upper bound** column is provider-reported usage
  plus $0.4096 for every attempt without a provider record, so it is an upper bound,
  not an invoice. The generated table below reports configured-rate dollars per
  decision from host usage instead.

## Results

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ upper bound | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| P1 | 2026-11-06 | Pilot (131k, 30/1) | S1 | 0.21 | Alive at stop (context capacity, both hosts) | 1 | — | 136 (25) | 6.05 | 859 | Mara Ellis, Evacuee; 08:00:00 → 08:12:22, Spring day 61. Crafted and wielded a pointy stick; looted a strip mall. Not scored. |
| C1 | 2026-11-06 | A0 (2-host handoff) | S1 | 5.49 | Alive at stop (orderly finish at the attempt reserve) | 4 | — | 233 (23) | 3.58 | 1,856 | Morgan Reed, Evacuee; 08:00:00 → 13:29:21, Spring day 61. Crafted fishing rod, foraged cattails, canned beans, clean water. Saved per player claim. |
| C2 | 2026-11-06 | A0 (2-host handoff) | S2 | 0.16 | Alive at stop (second voluntary handoff) | 0 | — | 158 (21) | 1.71 | 1,176 | Raelene Grant, chose Winter day 1; 08:00:17 → 08:09:49. Killed a feral; ocular zombie adjacent at stop. |
| C3 | 2026-11-06 | A0 (2-host handoff) | S1 | 0.10 | Alive at stop (second voluntary handoff) | 1 | — | 115 (23) | 0.84 | 740 | Alex Rowan, Evacuee; 08:00:00 → 08:05:50, Spring day 61. Crafted pointy stick. |

**Arm A0 is development data, not the ceiling.** Every A0 run ended at the
player's second voluntary handoff: the guide invites a handoff "when fresh context
helps", players took it at 96k–139k tokens of a 262k window, and the hidden 2-host
limit then ended the run at 115–233 of 250 attempts. The final actor is now offered
no handoff tool, so the five scored ceiling runs restart on that fix with the
configuration otherwise unchanged.

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ upper bound | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| T1 | 2026-11-06 | Ceiling | S1 | 0.59 | Alive at stop (orderly finish) | 4 | — | 231 (22) | 3.46 | 1,539 | Morgan Vale; 08:00 → 08:35:39. Pointy stick, 7 protein rations, clean water, emergency blanket and jacket. Recruited a follower. |
| T2 | 2026-11-06 | Ceiling | S2 | 0.05 | Died | 0 | Surrounded by zombies and ferals on a riverbank | 70 (—) | 0.52 | 425 | Russell Dobbs; chose a fitness-gym start among about 16 zombies. Memorial "Survived 2m". |
| T3 | 2026-11-06 | Ceiling | S1 | 0.61 | Alive at stop (orderly finish) | 2 | — | 231 (24) | 3.65 | 1,642 | Morgan Hale; 08:00 → 08:36:45. Foraged fiddleheads and leaves, stick. Recruited a follower. |
| T4 | 2026-11-06 | Ceiling | S2 | 0.03 | Died | 0 | Knocked down by a feral's thrown rock in a crowd | 37 (18) | 0.16 | 209 | Kathlyn Maloney; chose a candy-shop start among zombies. Memorial "Survived 1m". |
| T5 | 2026-11-06 | Ceiling | S1 | 2.11 | Alive at stop (orderly finish) | 4 | — | 237 (19) | 3.98 | 1,763 | Morgan Vale; 08:00 → 10:06:36. Ate a ration, clean water, medical supplies, wooden club. Saved per player claim. |

**Ceiling result (step 5).** Median survival is **0.59 h** (range 0.03–2.11 h)
against the 24 h rule, so under the pre-registered rule grounding is the
bottleneck and the aid arms begin. The adoption bar for an aid is a median of at
least 2.59 h. Two observations sit beside the rule and do not change it. First,
every S1 survivor was alive when its allowance ended, after 36–127 in-game minutes
for about 230 decisions: survival hours are bounded mainly by time scale, about
9–32 game seconds per request. Second, both deaths followed the player's own S2
choice of a dense urban start, and each came within 3 game minutes. The arm cost
$11.78 (unrounded OpenRouter generation-record totals, $11.777728; the rounded
column sums to $11.77). Dollar columns come from those per-generation records,
reconciled by the lead after each run; the custodian receipt itself carries only
the configured-rate estimate, which matched them.

### Aid arm A: zoom view (rejected)

Source `70eda9a` on the unmerged `aid-zoom-view` branch: `player_source` takes an
optional nearest-neighbour `zoom` of a crop, and the guide's tool row mentions it.

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ upper bound | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| A1 | 2026-11-06 | A (zoom) | S1 | 0.27 | Alive at stop (orderly finish) | 3 | — | 231 (18) | 3.54 | 1,610 | Morgan Hale. Protein ration, foraged cattails and fiddleheads, long pointy stick. 0 zoom uses. |
| A2 | 2026-11-06 | A (zoom) | S2 | — | Infrastructure failure | — | — | 76 (29) | 0.76 | 464 | Mid-stream provider error at request 76 (HTTP 200, then `stop_reason: error`); not scored, replaced by A6. |
| A3 | 2026-11-06 | A (zoom) | S1 | 0.30 | Alive at stop (orderly finish) | 1 | — | 234 (25) | 3.99 | 1,688 | Alex Rowan. Long pointy stick. One `player_source` read without zoom. |
| A4 | 2026-11-06 | A (zoom) | S2 | 2.11 | Alive at stop (orderly finish) | 3 | — | 236 (23) | 4.12 | 1,761 | Clay Foxtail; chose an evac shelter start. Ate a ration, picked up rations, digging stick. 0 zoom uses. |
| A5 | 2026-11-06 | A (zoom) | S1 | 0.93 | Alive at stop (orderly finish) | 5 | — | 234 (23) | 4.04 | 2,000 | Alex Morgan. Wooden club, rations, clean water, emergency jacket and blanket, dogbane. 0 zoom uses. |
| A6 | 2026-11-06 | A (zoom) | S2 | 0.07 | Died | 0 | Overrun on a road by about 51 zombies and ferals | 85 (24) | 0.95 | 639 | Buffy Shapiro; urban start with an infected arm. 0 zoom uses. |

**Arm A decision: rejected.** Median survival is 0.30 h against the ceiling's
0.59 h and the 2.59 h bar. The player never used zoom in any arm-A run, so this
rejects the aid for **no uptake**; it is not evidence about zoomed reading itself.
The branch stays unmerged. Arm cost $17.41, including the failed A2.

### Aid arm B: consult the game's own help (rejected)

Source `784d3ae` (differs from the ceiling source only in docs); the frozen
context is the guide plus a paragraph permitting the player to open the game's own
help, command and keybinding screens and to keep what it learns as memory records.

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ upper bound | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| B1 | 2026-11-06 | B (help) | S1 | 0.38 | Alive at stop (orderly finish) | 3 | — | 231 (13) | 3.49 | 2,016 | C. Townsend (player-chosen name). Wooden club, chocolate drink, flashlight; follower. Saved a keybinding `procedure` record. |
| B2 | 2026-11-06 | B (help) | S2 | 0.29 | Alive at stop (orderly finish) | 4 | — | 239 (16) | 3.64 | 2,282 | Carolynn Hardy; default scenario. Cattails, rations, clean water, mission reward of cattail jelly. Two keybinding `procedure` records. |
| B3 | 2026-11-06 | B (help) | S1 | 0.42 | Alive at stop (orderly finish) | 4 | — | 234 (16) | 4.02 | 2,108 | Timothy Lowery. Long pointy stick, fiddleheads, clean water, ration. Two self-correction records; no keybinding record. |
| B4 | 2026-11-06 | B (help) | S2 | 0.17 | Alive at stop (orderly finish) | 0 | — | 231 (16) | 3.45 | 2,266 | Li Avery; random sewage-plant start. Carried weight rose, but no pickup is separable from starting kit. Keybinding `procedure` record. |
| B5 | 2026-11-06 | B (help) | S1 | — | Infrastructure failure | — | — | 191 (17) | 2.61 | 1,425 | HTTP 403: the API key's $250 monthly limit was exhausted. The owner raised it. Not scored. |
| B6 | 2026-11-06 | B (help) | S1 | — | Infrastructure failure | — | — | 211 (—) | 3.13 | 1,518 | 429 from OpenRouter admission control with no message; not retried (#378). Not scored. |
| B7 | 2026-11-06 | B (help) | S1 | — | Infrastructure failure | — | — | 199 (—) | 3.56 | 1,439 | Admission-control 429 citing a low account balance during auto-refill (#379). Not scored. |
| B8 | 2026-11-06 | B (help) | S1 | — | Infrastructure failure | — | — | 172 (—) | 2.48 | 1,150 | HTTP 200, then a stream error before any event (#380). Not scored. |
| B9 | 2026-11-06 | B (help) | S1 | 0.70 | Alive at stop (orderly finish) | 4 | — | 231 (20) | 3.41 | 1,817 | Morgan Reed; farmhouse. Wooden club, water, clean water, ration, emergency blanket; killed a zombie. No keybinding record. |

**Arm B decision: rejected.** Median survival is 0.38 h against the ceiling's 0.59 h
and the 2.59 h bar, so the guide stays unchanged. This was the first aid with real
uptake: three of five players read the game's own keybinding screen and kept what
they learned as `procedure` records. Median verified improvements were 4, against
the ceiling's 2, and no arm-B survivor died. These are signals beside the rule, not
measured effects. The B5–B8 dollar figures include the $0.4096 worst-case
reservation for each failed attempt that had no provider record.

### Aid arm C: reflection lineage (rejected)

Source `c313346` (#380). The frozen context is the guide plus a paragraph asking the
player to record an `advice` reflection before it hands off or finishes, and when its
survivor dies. Each run's assignment carries the earlier arm-C players' reflections
as bounded, fallible historical data.

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ upper bound | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| C1 | 2026-11-06 | C (reflect) | S1 | 0.45 | Alive at stop (orderly finish) | 5 | — | 232 (22) | 4.09 | 1,800 | Morgan Hale; follower. Long pointy stick, rhubarb, rations, clean water, emergency jacket and blanket. Two reflections. One stream-start error, retried by #380. |
| C2 | 2026-11-06 | C (reflect) | S2 | 0.22 | Died | 5 | Caught by a feral soldier near a house | 196 (22) | 2.35 | 1,480 | Alex Rowan; follower. Club, water, honey, rations, first-aid kit, emergency clothing. Post-death reflection named the decisive error. |
| C3 | 2026-11-06 | C (reflect) | S1 | 0.49 | Alive at stop (orderly finish) | 1 | — | 232 (27) | 3.47 | 1,921 | Elias Reed; injured. Bandaged a torso wound; killed a tough zombie and two feral mechanics. Two reflections. |
| C4 | 2026-11-06 | C (reflect) | S2 | — | Custody safety stop | — | — | 30 (—) | 0.10 | 151 | Character-creation input expired during dispatch; uncertain delivery permanently fenced input, as designed. Not scored; replaced by C6. |
| C5 | 2026-11-06 | C (reflect) | S1 | 0.28 | Alive at stop (orderly finish) | 1 | — | 234 (33) | 3.81 | 1,702 | Evan Mercer. Foraged burdock and pine materials. **First organic local program of the loop**: a saved bounded walking routine, run twice to `done`. Saved and quit per the player. |
| C6 | 2026-11-06 | C (reflect) | S2 | 2.06 | Alive at stop (orderly finish) | 1 | — | 236 (26) | 3.57 | 1,832 | Avery Stone; evac shelter start. Drank (thirst "Slaked"); long auto-travel; withdrew from a deranged axeman. Two reflections. |

**Arm C decision: rejected.** Median survival is 0.45 h against the ceiling's 0.59 h
and the 2.59 h bar, so the guide stays unchanged. Uptake was complete: every scored
run wrote reflections (ten in all), C2's post-death reflection named its decisive
error, and C5 produced the loop's only organic local program. None of this moved
survival hours at n=5. Arm cost $17.38, including the $0.10 C4 stop and C1's
$0.41 retry reservation.

## Loop result and next step

| Arm | Median survival h | Range | Deaths | Median verified improvements | Uptake | Decision |
| --- | ---: | --- | ---: | ---: | --- | --- |
| Ceiling (Terra) | 0.59 | 0.03–2.11 | 2 of 5 | 2 | — | Baseline |
| A: zoom view | 0.30 | 0.07–2.11 | 1 of 5 | 3 | No zoom used | Rejected (no uptake) |
| B: game help | 0.38 | 0.17–0.70 | 0 of 5 | 4 | 3 of 5 saved keybindings | Rejected |
| C: reflection | 0.45 | 0.22–2.06 | 1 of 5 | 1 | 5 of 5 reflected; 1 program | Rejected |

The loop spent $88.54 of D2's $150. A frontier player through the pixels-and-keys
boundary plays competently in the short term: runs routinely gather food, water,
tools and weapons. Of 20 scored runs, 4 died. Three followed the player's own S2
choice of a dense urban start; one (C2) followed a tactical error in an
evac-shelter start, which its own reflection named. But no run reached even one
in-game day inside its allowance. **Within a 250-decision allowance the survival
metric is bounded by time scale:** about 230 decisions pass 10–130 game minutes,
roughly 9–32 game seconds per decision. A 2.59 h bar is therefore nearly
unreachable for any aid that does not change pacing. The aids did not isolate
perception: arm A had no uptake. The three longest runs (T5, A4, C6) and the only
organic program (C5) all passed game time cheaply, through activities,
auto-travel or a loop.

The recommended next step tests time scale directly rather than adding more
perception aids. Run a long-horizon Terra arm, for example three Evacuee runs of
about 1,500 decisions each (roughly $20–25 each by this loop's rate), and track
**game seconds per decision** beside survival hours. The question is whether
needs, rest and supplies hold once the clock passes a day, which is the first
point at which #145's seven-day question becomes observable. It needs two owner
decisions. First, a new spend envelope: about $61 of D2 remains. Second, either
more actors per admission or a longer context window: two hosts of a 262k window
hold roughly 350 decisions, and `campaign-run/4` allows at most two hosts. #164's
cadence criteria stay deferred until that baseline exists. Infrastructure lessons
are recorded as fixes #378–#380 and the actual-spend admission rule.

## Evaluator re-score and power check (#383)

The [run evaluator](contracts/evaluation.md) (core 1, CDDA binding 1) re-scored all
30 runs from their recorded frames, traces and memory stores. These are new,
generated rows. The hand-scored tables above are unchanged and remain the record of
the loop's decisions. Regenerate the table with
`python -m tools.evaluate evaluate-table .runtime/evaluations`.

| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ceil01 | pilot | S1 | budget | 0.21 | 129 | 7 | 5.0 | 0 · 0.00 h | 59% | 17 | 0.0469 | 96% |
| ceil02 | pre-loop | S1 | budget | 5.49 | 227 | 6 | 3.0 | 1 · 5.00 h | 63% | 19 | 0.0158 | 61% |
| ceil03 | pre-loop | S2 | budget | 0.16 | 151 | 7 | 2.0 | 0 · 0.00 h | 30% | 4 | 0.0113 | 49% |
| ceil04 | pre-loop | S1 | budget | 0.10 | 109 | 7 | 2.0 | 0 · 0.00 h | 63% | 14 | 0.0077 | 35% |
| ceil05 | ceiling | S1 | budget | 0.59 | 225 | 7 | 3.7 | 0 · 0.00 h | 71% | 16 | 0.0154 | 62% |
| ceil06 | ceiling | S2 | died | 0.05 | 65 | 7 | 2.2 | 0 · 0.00 h | 56% | 7 | 0.0081 | 45% |
| ceil07 | ceiling | S1 | budget | 0.61 | 223 | 7 | 3.0 | 0 · 0.00 h | 70% | 15 | 0.0164 | 66% |
| ceil08 | ceiling | S2 | died | 0.03 | 35 | 7 | 4.0 | 0 · 0.00 h | 21% | 3 | 0.0045 | 0% |
| ceil09 | ceiling | S1 | budget | 2.11 | 229 | 8 | 4.0 | 1 · 1.67 h | 60% | 17 | 0.0174 | 60% |
| aidA1 | zoom-aid | S1 | budget | 0.27 | 224 | 7 | 5.0 | 0 · 0.00 h | 62% | 14 | 0.0158 | 60% |
| aidA2 | zoom-aid | S2 | infrastructure | 0.12 | 74 | 7 | 2.0 | 0 · 0.00 h | 65% | 10 | 0.0089 | 49% |
| aidA3 | zoom-aid | S1 | budget | 0.30 | 226 | 7 | 4.0 | 0 · 0.00 h | 58% | 15 | 0.0176 | 62% |
| aidA4 | zoom-aid | S2 | budget | 2.11 | 229 | 7 | 3.0 | 1 · 1.65 h | 65% | 17 | 0.0180 | 64% |
| aidA5 | zoom-aid | S1 | budget | 0.93 | 226 | 9 | 6.0 | 0 · 0.00 h | 62% | 14 | 0.0179 | 63% |
| aidA6 | zoom-aid | S2 | died | 0.07 | 83 | 6 | 4.2 | 0 · 0.00 h | 49% | 16 | 0.0115 | 57% |
| aidB1 | game-help-aid | S1 | budget | 0.38 | 223 | 8 | 3.0 | 0 · 0.00 h | 65% | 18 | 0.0156 | 62% |
| aidB2 | game-help-aid | S2 | budget | 0.29 | 226 | 7 | 5.0 | 0 · 0.00 h | 56% | 22 | 0.0161 | 59% |
| aidB3 | game-help-aid | S1 | budget | 0.42 | 224 | 6 | 7.8 | 0 · 0.00 h | 53% | 16 | 0.0180 | 60% |
| aidB4 | game-help-aid | S2 | budget | 0.17 | 223 | 7 | 3.0 | 0 · 0.00 h | 44% | 20 | 0.0155 | 58% |
| aidB5 | game-help-aid | S1 | infrastructure | 0.20 | 185 | 7 | 3.0 | 0 · 0.00 h | 64% | 20 | 0.0119 | 54% |
| aidB6 | game-help-aid | S1 | infrastructure | 1.29 | 205 | 10 | 4.0 | 1 · 0.82 h | 77% | 23 | 0.0133 | 58% |
| aidB7 | game-help-aid | S1 | infrastructure | 0.37 | 193 | 7 | 5.0 | 0 · 0.00 h | 61% | 19 | 0.0163 | 62% |
| aidB8 | game-help-aid | S1 | infrastructure | 0.20 | 165 | 7 | 2.0 | 0 · 0.00 h | 66% | 28 | 0.0125 | 56% |
| aidB9 | game-help-aid | S1 | budget | 0.70 | 223 | 7 | 3.0 | 0 · 0.00 h | 59% | 14 | 0.0153 | 60% |
| aidC1 | reflection-aid | S1 | budget | 0.45 | 223 | 7 | 6.0 | 0 · 0.00 h | 60% | 13 | 0.0165 | 62% |
| aidC2 | reflection-aid | S2 | died | 0.22 | 188 | 7 | 2.8 | 0 · 0.00 h | 54% | 13 | 0.0125 | 53% |
| aidC3 | reflection-aid | S1 | budget | 0.49 | 223 | 15 | 3.0 | 0 · 0.00 h | 64% | 16 | 0.0156 | 61% |
| aidC4 | reflection-aid | S2 | custody | 0.00 | 23 | 7 | — | 0 · 0.00 h | 94% | 16 | 0.0040 | 0% |
| aidC5 | reflection-aid | S1 | budget | 0.28 | 222 | 17 | 4.0 | 0 · 0.00 h | 54% | 12 | 0.0171 | 61% |
| aidC6 | reflection-aid | S2 | budget | 2.06 | 226 | 17 | 4.0 | 1 · 1.45 h | 63% | 17 | 0.0158 | 58% |

- **Columns.**
  - *Game h* is survival within the run's last episode.
  - *End* is the censor reason.
  - *Setup* counts decisions before the first in-play frame.
  - *Routine pace* is the median game seconds per decision over clock intervals shorter
    than 15 minutes.
  - *Long activities* are single stretches advancing 15 minutes or more.
  - *Out of play* and *Longest stall* come from the mode reader.
  - *$ / decision* is configured-rate host usage.
  - *Large rewrites* is the share of spend in requests writing over 30,000 cache tokens.
- **Agreement with hand scores.** The evaluator matches the hand-scored survival hours
  on every scored run.
  - C2 now reads 0.22 h: its survivor started a second world, and the evaluator
    measures within the last episode.
  - B6's 1.29 h is an infrastructure-lost run that the hand tables did not score.
- **Reader validation.** Held-out frames from pre-loop sessions, labelled blind:
  - **Clock:** 115/115 exact.
  - **Needs:** 84/84 each.
  - **Mode:** 200/200 on a fresh sample after one fix.
  - **Death:** 240/240, but with no deaths in the samples, so recall is unmeasured.
  - **Threat:** 91/91 on empty creature lists only; counting creatures is not yet validated.
  - **Gap:** every held-out clock read Spring day 61 between 8 and 10 AM. Night, PM and
    day-rollover readings are covered only by synthetic tests until the first #382
    admission is checked by hand.
- **The game-help aid's target metric moved the wrong way.** The mean longest
  out-of-play streak was 18.0 decisions against the ceiling's 11.6 (+6.4, 95%
  bootstrap interval +1.2 to +12.2). Reading the in-game help is itself out of play,
  so the aid confounds its own metric.

**Power check (#383 decision D4).** The simulation is fitted to the 20 scored runs:
- an exponential death hazard of 0.319 per game hour
  (4 deaths in 12.54 game hours);
- censoring drawn from the alive runs' stopping times;
- 1,500 simulations per cell, two-sided α 0.05.

| Metric (test) | Effect | n = 5 per arm | n = 10 | n = 20 | n = 40 |
| --- | --- | ---: | ---: | ---: | ---: |
| Censored survival (log-rank) | 2× survival time | 1% | 5% | 12% | 21% |
| Censored survival (log-rank) | 3× survival time | 2% | 8% | 18% | 37% |
| Ladder progress beyond in-play (Fisher exact) | odds × 4 | 8% | 16% | 42% | 82% |
| Routine pace (Welch t on logs) | 1.5× | 44% | 80% | 98% | 100% |

At the #382 horizon (censoring about eight times later), three against three lineages
detect a 2× survival change 10% of the time.

**Decision under D4.** Censored survival and the milestone ladder do **not** become
the metric of record. They stay descriptive guards.
- With four deaths in 12.5 game hours and budget censoring, no affordable run count
  detects even a tripling of survival.
- At this run length the ladder rarely moves past "in play": 5 of 20 runs ate and
  1 drank.

Each change instead pre-registers a targeted process metric on its change page,
such as routine pace, stall length or the target failure's rate. Survival, cost and
setup serve as guards. Routine pace reaches 80% power for a 1.5× change at about 10
runs per arm.

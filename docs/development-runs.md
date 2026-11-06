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

D2's binding cap is the lower of its two limits: the pre-loop actual upper bound
($258.406176979 over 11,353 attempts, after #369) plus $150, which is
$408.406176979. Packages from C2 onward freeze that value as `ceiling_usd`; P1 and C1
were frozen at $410 and their worst cases fit either value. Each package also
freezes the current cumulative actual upper bound as `prior_reserved_usd`, so a run
is admissible only while the remaining headroom covers its full $102.40 worst
case, that is, while cumulative actual spend is at most $306.01. From $264.46 after
P1, that leaves about $41.5 of actual spend. At P1's $0.0445 per attempt a scored run
costs about $11, so **three or four scored runs are expected to fit, not five**.
When the next run no longer fits, the loop stops and asks the owner rather than
shrinking runs. The reservation is a worst case, not an invoice: actual spend stays
far below it.

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
- **Cost:** provider-reported dollars, charged attempts, setup attempts (until the
  first in-play frame) and wall seconds.

## Results

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ actual | Wall s | Note |
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

| Run | Date | Arm | Start | Survival h | Status | Verified improvements | Death cause | Attempts (setup) | $ actual | Wall s | Note |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- |
| T1 | 2026-11-06 | Ceiling | S1 | 0.59 | Alive at stop (orderly finish) | 4 | — | 231 (22) | 3.46 | 1,539 | Morgan Vale; 08:00 → 08:35:39. Pointy stick, 7 protein rations, clean water, emergency blanket and jacket. Recruited a follower. |
| T2 | 2026-11-06 | Ceiling | S2 | 0.05 | Died | 0 | Surrounded by zombies and ferals on a riverbank | 70 (—) | 0.52 | 425 | Russell Dobbs; chose a fitness-gym start among about 16 zombies. Memorial "Survived 2m". |
| T3 | 2026-11-06 | Ceiling | S1 | 0.61 | Alive at stop (orderly finish) | 2 | — | 231 (24) | 3.65 | 1,642 | Morgan Hale; 08:00 → 08:36:30. Foraged fiddleheads and leaves, stick. Recruited a follower. |
| T4 | 2026-11-06 | Ceiling | S2 | 0.03 | Died | 0 | Knocked down by a feral's thrown rock in a crowd | 37 (18) | 0.16 | 209 | Kathlyn Maloney; chose a candy-shop start among zombies. Memorial "Survived 1m". |
| T5 | 2026-11-06 | Ceiling | S1 | 2.11 | Alive at stop (orderly finish) | 4 | — | 237 (19) | 3.98 | 1,763 | Morgan Vale; 08:00 → 10:06:36. Ate a ration, clean water, medical supplies, wooden club. Saved per player claim. |

**Ceiling result (step 5).** Median survival is **0.59 h** (range 0.03–2.11 h)
against the 24 h rule, so under the pre-registered rule grounding is the
bottleneck and the aid arms begin. The adoption bar for an aid is a median of at
least 2.59 h. Two observations sit beside the rule and do not change it. First,
every S1 survivor was alive when its allowance ended, after 30–130 in-game minutes
for about 230 decisions: survival hours are bounded mainly by time scale, about
8–30 game seconds per request. Second, both deaths followed the player's own S2
choice of a dense urban start, and each came within 3 game minutes. The arm cost
$11.78.

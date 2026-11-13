---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Cadence plan of 13 November 2026 (#442): route options compared on latency and cost per game hour against the responsiveness criteria of #164, from recorded evidence and published figures read that day; whether the 2 s criterion should stand; owner decisions and costed measurements. No run, game launch or model call was made'
review_trigger: An owner decision on the list in this note, a new cadence measurement, or a change to the player route or to the phases of ADR 009
---

# Cadence plan: route options against the responsiveness criteria

The seven-day development lineage
([#397](https://github.com/CVX-Hull/enactive/issues/397)) measured the player's model
responses at 8.1–13.7 s at the 95th percentile (p95) against a 2 s criterion. This note
compares the route options that could change that, on latency and on cost per game
hour, and says what the criterion should become. It was written on 13 November 2026 for
[#442](https://github.com/CVX-Hull/enactive/issues/442) at \$0: no run, game launch or
model call. It proposes; the [owner decisions](#owner-decisions) at the end decide.

Every number cites a key from [Sources](#sources). Recorded evidence is from this
repository. Published figures were read on 13 November 2026 and are averages from
other workloads, so they are context, not measurements of this player
([S-EVIDENCE](../standards/evidence.md)). A figure marked *arithmetic* multiplies
recorded quantities by published prices; it is not a forecast.

## The criteria and what has been measured

[#164](https://github.com/CVX-Hull/enactive/issues/164) (useful apparent responsiveness
of the complete player) records the frozen criteria as (S12):

> Freeze and meet the original complete-configuration targets: 20 genuine independently
> evaluable useful routine decisions, new-decision→visible-effect p95≤2s, unexplained
> routine stall≤5s and supported local useful effect≤500ms. Preserve failed/censored
> decisions, full acquisition/repair/memory/setup/ending costs and novel/long-activity
> exceptions. Do not manufacture a cohort or trade quality for speed. Useful local
> execution may count; key/row/program counts do not.

Its state block of 9 November 2026 adds: "The criteria are unchanged; none is relaxed."

The seven-day development lineage reported them descriptively and did not apply them
(S3, lines 175–182):

| Criterion | Measured | What the measurement is |
| --- | --- | --- |
| New decision to visible effect, p95 ≤ 2 s | Model response per actor trace: median (p50) 4.7–8.2 s, p95 8.1–13.7 s, maximum 21.8 s | The model's response only. The criterion's interval also holds dispatch and the capture that shows the effect, so this is a lower bound on it |
| Unexplained routine stall ≤ 5 s | Longest single model response 21.8 s; the evaluator's longest streak was 14–31 decisions per admission | The evaluator's stall is a count of decisions outside play, not seconds without progress (S10) |
| Supported local useful effect ≤ 500 ms | Input send to receipt: p50 25 ms, p95 58 ms, maximum 619 ms (n = 9,125). Capture send to receipt: p95 392 ms | Mechanical delivery only. No program ran, so no local *useful effect* was timed |
| 20 useful decisions | Not measured | No validated reader of a useful decision exists |

Both figures in #442's brief are confirmed: model response p95 8.1–13.7 s and local
input p95 58 ms. Neither is the criterion's own interval.

The one decision ever timed over the criterion's full interval took 22.169 s from cue
to returned effect, of which 18.826 s were three model responses and 3.317 s were
dispatch to receipt, including 1.4 s of waits the player asked for (S5). That was the
selected finite configuration, DeepSeek Flash 1017 at medium effort (S14), whose live
responses measured p50 11.8 s and p95 24.7–27.5 s (S13).

## Baseline: where time and money go

Development runs use a diagnostic route: OpenRouter, `openai/gpt-6.1-terra`, pinned to
provider `openai`, medium effort, default tier, with a 262,144-token window and 39
images (S7). Its day-scale lineages, from the run ledger (S1, S2; the long-horizon
arm's elapsed hours are its record's, S4):

| Lineage | Game hours | Decisions | Spend | Dollars per game hour | Dollars per decision | Decisions per game hour | Wall seconds per decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long-horizon arm (#382), first lineage | 24.71 | 638 | \$13.18 | 0.53 | 0.021 | 26 | 7.5 |
| Long-horizon arm (#382), second lineage | 25.04 | 618 | \$13.60 | 0.54 | 0.022 | 25 | 7.5 |
| Seven-day development lineage (#397) | 47.79 | 1,915 | \$38.40 | 0.80 | 0.020 | 40 | 8.1 |
| Held-out lineage for the curator memory study (#522) | 27.76 | 1,753 | \$30.11 | 1.08 | 0.017 | 63 | 9.5 |

The long-horizon arm's third lineage stopped at 0.54 game hours and is left out (S4,
lines 264–267). Three things follow for the options below.

- **Cost per game hour is mostly decisions per game hour.** Dollars per decision stay
  between \$0.016 and \$0.023 across the seven-day development lineage's admissions,
  while dollars per game hour run from \$0.38 to \$6.61 (S3, lines 121–129 and 170–171).
  84.4% of its game time passed inside long activities such as sleep and crafting
  (S3, line 134).
- **Spend is prompt, not output.** Of the lineage's \$38.40, 72.9% was cache writes,
  23.8% cache reads and 3.3% output; the median prompt was 93,828 tokens (S6, lines
  32–35). That is about 130 output tokens per request (*arithmetic*: 3.3% of \$38.40 at
  \$5 per million over 1,978 requests). 63.5% of spend sat in the 8.04% of requests
  that rewrote more than half the prompt (S6, line 36).
- **The observer sees bursts and waits.** A decision sends about 4.8 inputs (9,125
  input requests over 1,915 decisions; S3, lines 133 and 151), each delivered in tens
  of milliseconds, then the screen waits about 8 s for the next response. One game hour
  took 326 s of wall time in that lineage (S1, S2).

## Route options

"Published" is the time to first answer token, which includes reasoning time, and the
output speed in tokens per second, as averages over the past five days of benchmark
runs (S20, S21). The benchmark's method describes no image workload. The figures are
not 95th percentiles and not this player's prompt. Where a page's table and text
disagree, both values are given.

| Option | Recorded here | Published, read 13 November 2026 | Cost per game hour | Against 2 s |
| --- | --- | --- | --- | --- |
| **Current diagnostic route:** GPT-6.1 Terra, medium effort, default tier | p50 4.7–8.2 s, p95 8.1–13.7 s (S3) | First answer token 4.73–4.85 s; 63 tokens per second | \$0.80 measured; \$0.53–1.08 across four lineages (S1, S2) | Misses by four to seven times |
| **Effort setting:** the same model at low or no reasoning. The model accepts none, low, medium (the default), high, xhigh and max (S17) | None on this model. On DeepSeek Flash 1017, turning reasoning off cut the median from 12.524 s to 1.415 s on six retained screens each, and grounded positive replies fell from 2 of 4 to 1 of 4; no reply was both grounded and within 1.5 s (S5) | Low: 2.67–2.76 s. None: 2.14–2.20 s; 63–65 tokens per second | Same prices. Output is 3.3% of spend, so about \$0.78–0.80 if decisions per game hour do not change (*arithmetic*) | Misses: the first answer token alone takes over 2 s on the benchmark's prompts, which carry no images |
| **Service tier:** the same model on Fast mode, the provider's priority tier | None | "up to 2.5× faster", stated for another model; prices are twice the standard rate (S17, S19). OpenRouter lists it at \$2.00 input and \$10.00 output per million (S16) | \$1.60 (*arithmetic*: twice \$0.80) | Misses even if the full multiplier applied: p95 3.2–5.5 s (*arithmetic*) |
| **Smaller tier:** GPT-6 Luna ([#25](https://github.com/CVX-Hull/enactive/issues/25), whether a smaller tactical model earns its complexity) | None on the current interface | Medium: 5.22–6.26 s. Low: 2.91–3.26 s. None: 1.61–1.74 s; 89–95 tokens per second. Prices are a tenth of Terra's, cache reads a fifth (S15, S18) | About \$0.10 (*arithmetic*: the recorded token mix at Luna's prices, decisions unchanged) | At medium effort it reaches its first answer token later than Terra. Only no reasoning comes under 2 s, before any tool call completes |
| **Other provider:** DeepSeek V4.1 Flash 1017, the selected finite configuration (S14) | Medium: p50 11.8 s, p95 24.7–27.5 s live (S13). No reasoning: median 1.415 s on retained screens, with grounding lost as above (S5) | No reasoning, the earlier listing of this model: 0.90 s and 204 tokens per second, median across providers. 48 endpoints from \$0.03 to \$0.60 input per million (S16) | About \$0.25 at the Fireworks US endpoint's prices (*arithmetic*; cache writes priced as input, because the endpoint lists no cache-write price) | Medium misses by more than the current route. No reasoning is the only recorded setting under 2 s, and it missed the useful choice |
| **Other provider:** Claude Haiku 5.5 | None on the current interface | Low: 6.35 s. Medium: 10.08 s. Prices equal Luna's up to 100,000 prompt tokens and are five times higher above (S16) | \$0.10–0.50 (*arithmetic*); the recorded median prompt is 93,828 tokens and the 90th percentile 197,459 (S6) | Misses |
| **Other provider:** Gemini 3.5 Flash-Lite | None on the current interface | 4.71 s; 293 tokens per second; \$0.30 input and \$2.50 output per million (S16) | Not computed: its cache price is not a write-and-read pair | Misses |
| **Programs on the actor's interface** (the programs and monitor phase of [ADR 009](../decisions/009-curated-player.md#programs)) | A model-free step is a capture and an input: p95 392 ms and 58 ms (S3); an earlier local loop measured 362–379 ms per linked capture (S5). Use so far: one program in the current design, and no organic program run in any #164 recording (S8, line 51; S5) | Not applicable | Each decision moved to a model-free step removes about \$0.02 and 8 s. Supervising turns and model calls inside programs add cost back, unmeasured | The only option whose steps fit inside 2 s and 500 ms. It applies only to decisions a program can take |
| **Required emissions and snapshot diffs** (ADR 009's [emissions](../decisions/009-curated-player.md#actor-emissions-d10) and [diffs](../decisions/009-curated-player.md#reaching-the-actor-without-latency-d2)): a cost, not a lever | One 200-token diff adds \$0.00106–0.00262, 5.5–13.5% of an average request (S6, lines 48–55). Emissions are unmeasured: the tool schema has no such fields and every sealed trace predates them | Not applicable | A 200-token diff on every request: \$0.04–0.11 more. Every 50 tokens of emission text per call: \$0.02–0.04 more (*arithmetic*) | Moves away from it: 50 more output tokens take up to 0.8 s at 63 tokens per second (*arithmetic*) |

## What the comparison shows

1. **No route with reasoning on comes near 2 s.** Every published first-answer time
   for a reasoning setting is between 2.7 s and 10.1 s, on benchmark prompts with no
   images. The smaller tiers are cheaper, not quicker to answer: Luna at medium effort
   is slower to its first answer token than Terra at medium.
2. **The settings under 2 s all turn reasoning off,** and the one recorded test of that
   trade lost the useful choice (S5). It ran on six retained screens with shortened
   context, so it is a screen, not a result about play.
3. **Output length does not explain the response time.** About 130 output tokens take
   no more than about 2 s at the published 63 tokens per second, against a median
   response of 4.7–8.2 s. The record does not say whether that count includes reasoning
   tokens, so the rest may be reasoning, the wait before the first token, or both.
4. **Pace moves cost per game hour as much as price does.** Across the priced options
   the *arithmetic* runs from about \$0.10 to \$1.60 per game hour. Within one lineage
   on one route, admissions ran from \$0.38 to \$6.61 per game hour. Fewer model
   decisions per game hour cuts cost on any route.
5. **A model call inside every counted decision cannot meet the criterion.** With model
   responses at p95 8–14 s, a 2 s p95 over all decisions needs about 95% of them to be
   taken locally (*arithmetic*). Programs are the only option here that takes decisions
   locally, and none has yet run in play.

## Should the 2 s criterion stand?

**Recommendation: keep the numbers, and change what is measured.** The reasons:

- **The charter's rule is about the observer, and already allows a slow model.** "A
  slower model is acceptable only where useful execution covers its delay and the
  complete configuration still meets the declared cadence", with "loading and long
  activities separately visible and bounded" (S11). The criterion's own text says
  "Useful local execution may count." Relaxing 2 s to fit a model call would drop that
  rule; keeping it points the work at local execution.
- **It has never been measured as written.** The seven-day development lineage
  measured model response time, a part of the interval. The interval's population,
  useful routine decisions, has no validated reader, and a cohort of 20 was judged
  unlikely to be collectable: 0.14% in the middle scenario of the feasibility pass
  (S5).
- **Route selection cannot reach it,** as the comparison shows, so holding the
  criterion against the route decides nothing. Holding it against the complete
  configuration, programs included, decides something.

The restated measurement, for the owner to accept or change:

1. **Interval:** from the receipt of the capture a decision is made on, to the receipt
   of the first capture after its first input. The shelter diagnostic was timed this
   way from host receipts (S5), so no new instrumentation is expected.
2. **Population:** every routine decision in play, not only decisions labelled useful.
   Setup, long activities, loading and endings are reported separately with their own
   bounds, as the charter asks. Decisions taken by a program count like the actor's.
3. **Targets unchanged:** p95 ≤ 2 s on that interval, no unexplained routine gap over
   5 s, and a program's step ≤ 500 ms from its capture to the capture showing its
   effect.
4. **Quality guard unchanged:** 20 useful decisions, labelled by hand by two reviewers
   from frames, so speed is not bought with useless play.
5. **Model response time** (p50, p95, maximum per actor trace) is reported as a
   diagnostic, not as the criterion.

Under this measurement the current route is still expected to fail, because the
interval adds dispatch and capture to a response that already exceeds it. #164 then
stays unqualified until programs take most routine decisions.

## Interaction with memory work

Owner premise, 13 November 2026, given with this note's brief: long-term memory is
settled before any seven-day or other long run. Nothing here proposes a long run. Each
option meets that work differently.

| Option | Interaction with memory work |
| --- | --- |
| Effort setting | Memory adds context to read on every decision: a snapshot, its diffs, an ontology card (S8, lines 241–257). Whether an actor with little or no reasoning uses pushed memory is untested; the one recorded test of no reasoning lost grounding on a shortened context (S5). The curator memory study scored traces of Terra at medium effort (S3, line 46; S4), so its results would not carry to another setting |
| Service tier | Independent of the memory design. It doubles the price of every token memory adds |
| Smaller tier | A second model. Replacing the actor leaves the memory evidence, all on Terra traces, without a subject. Beside the actor, the recorded cost of a curator on Terra is \$0.49 per game hour on the seven-day development lineage (S9, line 73), about five times a Luna actor's \$0.10, so memory work would be most of the spend |
| Other provider | Cache pricing differs: DeepSeek endpoints list no cache-write price and cache implicitly (S16). The snapshot-diff estimate does not transfer to other routes (S6, lines 74–80) and would be measured again |
| Programs | The most dependent. Programs live in the knowledge repository, are induced, fitted and retired by the curator, and use the actor's expectations as success predicates (S8, lines 289–299 and 366–379). The curator and memory phase is not adopted and its study closed with a registered no-go (S8, lines 670–676), so who writes and curates programs is open until memory is settled |
| Emissions and diffs | These are memory's own cost to cadence: more output per decision and more prompt per request. Every figure above is for a prompt without them |

The consequence for order: memory will change the prompt's size, its cache behaviour and
possibly the number of models. A route measured now is measured on a prompt that is
about to change.

## Proposed measurements

**Offline re-measurement of the criterion's interval, \$0.** Compute the restated
interval over the sealed host traces of the seven-day development lineage and the
long-horizon arm, starting from the existing `host-summary` distributions of response
and tool times
([evaluation contract](../contracts/evaluation.md#diagnostics-owned-by-this-contract)).
It gives the first distribution of the criterion's own interval, split into response,
dispatch and capture, and the share of decisions already under 2 s. No model is called.
Stop condition: none needed; it reads sealed evidence only.

**Retained-prefix replay probe, at most \$65.** It answers one question: on this
player's real prompts, does any setting bring responses under 5 s without losing
grounding?

- **Inputs:** 10 decision points drawn by a seeded sample across the 14 actors of the
  sealed seven-day development lineage (S6, line 15), frozen with their hashes before
  any call. No game runs and no tool call is executed.
- **Settings, six:** Terra at medium effort on the default tier as the reference;
  Terra low; Terra with no reasoning; Terra medium on Fast mode; Luna medium; Luna with
  no reasoning.
- **Requests:** for each decision point and setting, the actor's previous request once,
  to warm the provider cache as live play does, then the decision's own request twice:
  180 requests.
- **Measures:** time to first answer token and to completion; provider-reported cost;
  and the proposed tool call, rated grounded or not by two reviewers blind to the
  setting.
- **Cost:** about \$8 expected (*arithmetic* from the recorded median prompt of 93,828
  tokens, 83,548 of them read from cache; S6, line 34). The worst case is \$63.90:
  every request priced at the route's \$0.4096 for a request with no cost record (S7),
  twice that on Fast mode and a tenth on Luna.
- **Stop conditions:**
  - a pilot of one decision point through all six settings comes first; stop if any
    response lacks its cost, usage or end-of-stream marker, or reports a model,
    provider or service tier other than the one requested (Fast mode can fall back to
    the default tier; S19);
  - stop at \$65 of provider-reported cost, counted per response as a player run's
    [spend limit](../operations/campaign-run.md#spend-limit) counts it;
  - stop if the reference's median completion falls outside the live 4.7–8.2 s,
    because the replay then does not reproduce live latency;
  - stop a setting after five decision points if none of its completions is under 5 s.
- **Reading, fixed before it runs:** a setting is a candidate for a later development
  run only if its p95 completion is at most 5 s and its grounded count is no more than
  two below the reference's of 20. Otherwise route settings are closed as a cadence
  lever. With 10 decision points this is a screen, not a qualification.

## Owner decisions

1. **The 2 s criterion.**
   - (a) Leave it as written and unmeasured.
   - (b) Keep the numbers and adopt the restated measurement above.
   - (c) Restate it with a separate, looser bound for decisions the model takes.

   Recommendation: (b). It keeps the charter's rule and makes the criterion measurable
   on evidence already sealed.
2. **Order against memory work.**
   - (a) Change the route for cadence now.
   - (b) Settle memory first and hold route changes until its context shape is frozen.

   Recommendation: (b), which follows the owner's premise of 13 November 2026.
3. **The route for development runs until then.**
   - (a) Keep GPT-6.1 Terra at medium effort on the default tier.
   - (b) Lower its effort.
   - (c) Move it to Fast mode at twice the price.
   - (d) Move to GPT-6 Luna.
   - (e) Return to the selected DeepSeek configuration.

   Recommendation: (a). It is the route every day-scale lineage and the memory evidence
   were recorded on, and no alternative is shown to reach the criterion.
4. **The smaller tactical tier (#25).** Its revisit trigger has fired: the single-model
   route cannot meet its latency target (#25, state block of 7 November 2026).
   - (a) Adopt a smaller model as the actor.
   - (b) Reject a smaller tier.
   - (c) Defer it as the actor, and keep #25 as the place where small models are bound
     to the monitor and to model calls inside programs, each on recorded cases.

   Recommendation: (c). Published figures show a smaller tier is cheaper but not
   quicker with reasoning on, and nothing recorded shows it can play.
5. **Where #164 is qualified.**
   - (a) Against the route alone.
   - (b) Against the complete configuration once the programs and monitor phase exists,
     with program steps measured against 500 ms there.

   Recommendation: (b). Programs are the only option whose steps fit the criteria.
6. **Budgets for emissions and snapshot diffs.**
   - (a) Carry the snapshot-diff note's caps, about 200 tokens per diff and 2,000 live
     (S6, lines 63–66), add a token cap on emission text per call, and measure both in
     the first run that has them.
   - (b) Set no cap until they are measured.

   Recommendation: (a). Each is a direct, per-decision cost in time and money.
7. **The offline re-measurement, \$0.** Approve or decline.

   Recommendation: approve. It needs decision 1 only for which interval to report.
8. **The retained-prefix replay probe, at most \$65.**
   - (a) Do not run it.
   - (b) Run it now.
   - (c) Run it once the memory work has frozen the actor's context shape.

   Recommendation: (c). The probe replays prompts, and memory is about to change them.

## What this note cannot show

- **Published latency is not this player's latency.** The figures are averages of run
  medians on text prompts of about 1,000 to 100,000 tokens and on agentic tasks (S20).
  None is a 95th percentile, and none carries 39 images.
- **No provider page gives a latency number.** OpenAI's model pages state prices and
  effort settings only (S17, S18). OpenRouter's public endpoint list leaves its latency
  and throughput fields empty (S16). The latency figures are a third party's benchmark
  (S21), primary for its own measurements only.
- **The published pages were read as converted text,** not in a browser, and the
  benchmark's tables and text disagree by up to about 1 s on the same page.
- **Not found in any source read:** a speed multiplier for Fast mode on GPT-6.1 Terra,
  a latency figure for the half-price flex tier that the endpoint list also offers
  (S16), and any latency figure for Claude Haiku 5.5 with reasoning off.
- **Every arithmetic cost assumes the recorded token mix and decisions per game hour.**
  A different model tokenises, reasons and plays differently; nothing here measures
  that.
- **The owner premise on memory** is recorded here from this note's brief; it has no
  dated record yet.

## Sources

Line numbers are at commit `7267be3`.

**Recorded in this repository**

| Key | Source |
| --- | --- |
| S1 | [Run ledger](../../data/evaluation/runs.jsonl): rows 31–37 (#382), 38–44 (#397) and 45–52 (#522), by the row's `study` field. `python -m tools.run_ledger totals --study ISSUE` reproduces attempts, wall seconds and spend |
| S2 | [Metrics snapshot](../../data/evaluation/run-metrics.jsonl): rows 31–37 (#382), 38–45 (#522) and 46–52 (#397), fields `decisions` and `survival.game_hours` |
| S3 | [Seven-day development lineage record](../acceptance/2026-11-07-seven-day-397.md): route, line 46; evaluator table, lines 121–129; lineage row, lines 132–136; input latency, lines 150–154; cost per day, lines 162–173; cadence table, lines 175–182 |
| S4 | [Long-horizon arm record](../acceptance/2026-11-07-long-horizon-382.md): lineage rows, lines 172–177, 218–226 and 264–267; arm result, lines 288–304 |
| S5 | [#164 iteration runs index](../acceptance/2026-11-04-issue164-runs.md), lines 30–32, and the published results it indexes: [cohort feasibility](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6623249182), [shelter diagnostic](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6638682260), [cadence readback](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6638915297) and [retained-screen test](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6639614118) |
| S6 | [Snapshot-diff cost](snapshot-diff-cost.md): lines 15, 25–26, 32–38, 48–55, 63–66 and 74–86 |
| S7 | [Development runs](../development-runs.md#benchmark): route, context and prices, lines 70–84 |
| S8 | [ADR 009](../decisions/009-curated-player.md): lines 51–56, 241–287, 289–379, 593–601 and 646–686 |
| S9 | [Curator shadow sessions record](../acceptance/2026-11-08-curator-shadow-454.md): results, lines 71–78 |
| S10 | [Evaluation contract](../contracts/evaluation.md): the stall event, line 121, and `stall.longest`, line 223 |
| S11 | [Charter](../charter.md): the responsiveness rule, lines 60–65 |
| S12 | [#164](https://github.com/CVX-Hull/enactive/issues/164), issue body read 13 November 2026: the first item under "Remaining qualification" and the state block of 9 November 2026 |
| S13 | [Observed effects record](../acceptance/2026-10-30-observed-effects.md): complete response p50 and p95, line 164 |
| S14 | [Overview](../overview.md): the selected finite configuration, lines 34–35 |

**Published, retrieved 13 November 2026**

| Key | Title and address | Used for |
| --- | --- | --- |
| S15 | OpenRouter, public model list: <https://openrouter.ai/api/v1/models> | Prices per million tokens of every model named |
| S16 | OpenRouter, public endpoint lists: <https://openrouter.ai/api/v1/models/openai/gpt-6.1-terra/endpoints>, and the same address for `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash-1017`, `anthropic/claude-haiku-5.5` and `google/gemini-3.5-flash-lite` | Prices by provider and service tier; the long-prompt thresholds; the empty latency and throughput fields |
| S17 | OpenAI, "GPT-6.1 Terra": <https://developers.openai.com/api/docs/models/gpt-6.1-terra> | Effort values; \$1, \$0.05 and \$5 per million for input, cached input and output; cache writes \$1.25; Fast mode at twice the standard rate |
| S18 | OpenAI, "GPT-6 Luna": <https://developers.openai.com/api/docs/models/gpt-6-luna> | \$0.10, \$0.01 and \$0.50 per million; cache writes \$0.125; image input supported |
| S19 | OpenAI, "Fast mode": <https://developers.openai.com/api/docs/guides/fast-mode> | "up to 2.5× faster", stated for `gpt-5.6-sol`; the fall-back to the default tier |
| S20 | Artificial Analysis, "Language Model API Performance Benchmarking", version 3.0.0 of 3 November 2026: <https://artificialanalysis.ai/methodology/performance-benchmarking> | Definitions, workloads and averaging of the latency figures |
| S21 | Artificial Analysis model and provider pages, each at <https://artificialanalysis.ai/models/> followed by its name: `gpt-6-1-terra-medium`, `gpt-6-1-terra-low`, `gpt-6-1-terra-non-reasoning`, `gpt-6-luna-medium`, `gpt-6-luna-low`, `gpt-6-luna-non-reasoning`, `deepseek-v4-1-flash-non-reasoning` and `gemini-3-5-flash-lite`, each with its `/providers` page where two values are given; and <https://artificialanalysis.ai/providers/anthropic> for Claude Haiku 5.5 | Time to first answer token and output speed |

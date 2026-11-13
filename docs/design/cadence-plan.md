---
owner: lead
status: historical
date: '2026-11-13'
scope: 'Cadence plan of 13 November 2026 (#442): route options compared on latency and cost per game hour against the responsiveness criteria of #164, from recorded evidence, an offline reading of the sealed traces and published figures read that day; whether the 2 s criterion should stand; owner decisions and costed measurements. No run, game launch or model call was made'
review_trigger: An owner decision on the list in this note, a new cadence measurement, or a change to the player route, to the memory design or to the phases of ADR 009
---

# Cadence plan: route options against the responsiveness criteria

**Status: decided.** This is the note as reviewed, kept as dated rationale. The owner's
answers to its nine questions are in the
[owner decision log](../decisions/owner-decisions.md).

The seven-day development lineage
([#397](https://github.com/CVX-Hull/enactive/issues/397)) measured the player's model
responses at 8.1–13.7 s at the 95th percentile (p95) against a 2 s criterion. This note
compares the route options that could change that, on latency and on cost per game
hour, and says whether the criterion should stand. It was written on 13 November 2026
for [#442](https://github.com/CVX-Hull/enactive/issues/442) at \$0: no run, game launch
or model call. It proposes; the [owner decisions](#owner-decisions) at the end decide.

In short: on this route the size of the prompt, not the reasoning setting, is the
largest recorded driver of response time; no option reaches 2 s while a model call sits
inside every decision; and the criterion should stand as written.

Every number cites a key from [Sources](#sources). Recorded evidence is from this
repository and its sealed evidence store. Published figures were read on 13 November
2026 and come from other workloads, so they are context, not measurements of this
player ([S-EVIDENCE](../standards/evidence.md)). A figure marked *arithmetic*
multiplies recorded quantities by published prices; it is not a forecast.

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
| New decision to visible effect, p95 ≤ 2 s | Model response per actor trace: median (p50) 4.7–8.2 s, p95 8.1–13.7 s, maximum 21.8 s | The model's response only. The criterion's interval runs from cue to verified effect and can hold several requests, so this is a lower bound on it |
| Unexplained routine stall ≤ 5 s | Longest single model response 21.8 s; the evaluator's longest streak was 14–31 decisions per admission | The evaluator's stall is a count of decisions outside play, not seconds without progress (S10) |
| Supported local useful effect ≤ 500 ms | Input send to receipt: p50 25 ms, p95 58 ms, maximum 619 ms (n = 9,125). Capture send to receipt: p95 392 ms | Mechanical delivery only. No program ran, so no local *useful effect* was timed |
| 20 useful decisions | Not measured | No validated reader of a useful decision exists |

Both figures in #442's brief are confirmed: model response p95 8.1–13.7 s and local
input p95 58 ms. Neither is the criterion's own interval.

One decision has been timed over the criterion's full interval. The shelter diagnostic
took 22.169 s from the first sufficient cue to the verified effect, across three
requests: 18.826 s in the three model responses and 3.317 s from dispatch to receipt,
including 1.4 s of waits the player asked for (S5). That was the selected finite
configuration, DeepSeek Flash 1017 at medium effort (S14), pinned to Fireworks US. Its
three diagnostic starts on that route had median responses of 3.822 s, 5.994 s and
13.654 s over 56 requests, 4 of them within 2 s (S5). An earlier pair of runs pinned
to BaseTen, with a 30-image context, measured p50 11.8 s and p95 24.7–27.5 s (S13,
lines 36–37 and 164).

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
| Held-out lineage for the curator memory study (#522) | 27.76 | 1,753 | \$28.88 | 1.04 | 0.016 | 63 | 9.5 |

The held-out lineage's row is its seven played admissions; a further \$1.23 went to an
admission lost to infrastructure before play (S16, line 95). The long-horizon arm's
third lineage stopped at 0.54 game hours and is left out (S4, lines 264–267).

- **Cost per game hour is mostly decisions per game hour.** Dollars per decision stay
  between \$0.016 and \$0.023 across the seven-day development lineage's admissions
  (S3, lines 121–129), while dollars per game hour run from \$0.37 to \$6.61 (S1, S2:
  rows `sd1a2` and `sd1a5`). 84.4% of its game time passed inside long activities such
  as sleep and crafting (S3, line 134).
- **Spend is prompt, not output.** Of the lineage's \$38.40, 72.9% was cache writes,
  23.8% cache reads and 3.3% output; the median prompt was 93,828 tokens (S6, lines
  32–35). 63.5% of spend sat in the 8.04% of requests that rewrote more than half the
  prompt (S6, line 36).
- **The observer sees bursts and waits.** A decision sends about 4.8 inputs (9,125
  input requests over 1,915 decisions; S3, lines 133 and 151), each delivered in tens
  of milliseconds, then the screen waits about 8 s for the next response. One game hour
  took 326 s of wall time in that lineage (S1, S2).

## What the sealed traces show

#164's remaining work asks for an assessment of context growth, cache use, reasoning
and output, host overheads, tool intervals and exposed stalls (S12, the third item
under "Remaining qualification"). The sealed host traces of the seven-day development
lineage answer part of it at \$0.

**Method.** Computed on 13 November 2026 by a read-only script over the 14 `host.jsonl`
traces of that lineage (S15): 1,978 requests, every one with usage. Durations are
differences of `monotonic_ms` on one host clock. A response runs from `request-start`
to `response-complete`; its stages end at `response-headers` and at the first
tool-argument delta in `response_progress`. Prompt tokens are `usage.input +
usage.cacheRead + usage.cacheWrite`. Percentiles interpolate linearly; the memory
note's nearest-rank values for the smallest and largest bands are 5.3 s and 14.0 s. The
script is not a tracked tool ([decision 8](#owner-decisions)). The lead and the
independent review of this note each recomputed both tables from the same traces and
matched them, apart from the corrections made since.

| Quantity | n | p50 | p95 | Other |
| --- | ---: | ---: | ---: | --- |
| Response, request sent to complete | 1,978 | 7.0 s | 12.2 s | 1.6% within 2 s; 20.5% within 5 s; maximum 21.8 s |
| Request sent to response headers | 1,978 | 3.0 s | 6.8 s | |
| Request sent to first tool-argument token | 1,978 | 5.4 s | 10.0 s | |
| First tool-argument token to complete | 1,978 | 1.4 s | 2.8 s | Output arrives at about 80 to 130 tokens per second, depending on whether reasoning tokens and the time before the first argument are counted |
| Responses that used no reasoning tokens | 128 | 4.7 s | 9.8 s | Their median prompt was 70,513 tokens |
| One request's first tool result to the next request's first tool result, any tool | 1,955 | 7.6 s | 12.9 s | 0.1% within 2 s; 13.9% within 5 s |
| Input tool call, start to result | 1,923 | 0.44 s | 1.62 s | |
| Image projection and request preparation in the host | 1,978 | 4.3 ms and 0.5 ms | 15.4 ms and 0.9 ms | |

Output averaged 126.7 tokens per response (median 96, maximum 1,051). Reasoning is
counted inside it and averaged 44.3 tokens (median 23).

By prompt size:

| Prompt tokens | Requests | p50 | p95 | Within 5 s | Mean cost per request | Share of spend | Images, median | Request body, median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Under 20,000 | 160 | 2.7 s | 5.2 s | 93.8% | \$0.0030 | 1.3% | 5 | 0.6 MB |
| 20,000–60,000 | 386 | 5.1 s | 8.0 s | 48.2% | \$0.0062 | 6.2% | 24 | 3.3 MB |
| 60,000–100,000 | 514 | 6.9 s | 11.4 s | 10.3% | \$0.0150 | 20.1% | 35 | 5.7 MB |
| 100,000–150,000 | 421 | 7.7 s | 11.7 s | 3.3% | \$0.0234 | 25.6% | 35 | 6.6 MB |
| Over 150,000 | 497 | 9.0 s | 13.9 s | 0.4% | \$0.0362 | 46.8% | 35 | 7.6 MB |

What this supports:

- **Prompt size is the largest recorded driver of response time on this route.** The
  median response more than triples from the smallest prompts to the largest.
- **Reasoning is a small part of it.** Reasoning averages 44 tokens, and the responses
  with none still took 4.7 s at the median. They are requests where the model chose not
  to reason, not a test of a setting.
- **Most of a response is the wait before any output.** The headers arrive at a median
  of 3.0 s and the first tool-argument token at 5.4 s; writing the tool call then takes
  1.4 s.
- **The large prompts carry the money too.** Requests over 100,000 tokens are 46% of
  requests and 72% of spend.
- **The host and the input path are not the delay:** milliseconds in the host and
  under half a second for an input call.

What it does not show. Prompt size is confounded with position in an actor's run (rank
correlation 0.99), with the number of images and with the size of the request body.
The smallest prompts all fall within an actor's first 14 requests, which include
loading and menus. Output also grows with the prompt, from 73 to 157 tokens on average. So the
table does not say which of tokens, images or upload causes the delay, or what a long
conversation cut short would do to play. It is one lineage on one route on one day. The
host records no time for server inference, model attention or physical display, so
those parts of #164's third item stay unknown, as do retrieval and repair costs.

## Route options

The published column is a third party's benchmark, Artificial Analysis, not the
providers' own statement (S23, S24). It gives two figures: the time to the first answer
token averaged over the benchmark's workloads, and the time to the first token on its
100,000-token workload, the closest to this player's median prompt. Both are averages
of run medians over five days; neither is a 95th percentile, and the method describes
no image workload.

| Option | Recorded here | Artificial Analysis (third party), read 13 November 2026: all workloads; 100,000-token prompt | Cost per game hour | Against 2 s |
| --- | --- | --- | --- | --- |
| **Current diagnostic route:** GPT-6.1 Terra, medium effort, default tier | p50 7.0 s, p95 12.2 s; per actor p95 8.1–13.7 s (S15, S3) | 4.85 s; 9.45 s | \$0.80 measured; \$0.53–1.04 across four lineages (S1, S2) | Misses by four to seven times |
| **Bound the context:** hand off earlier, [compact the conversation](long-horizon-memory.md#7-compact-the-conversation-instead-of-handing-off) or [rebuild the prompt at each decision](long-horizon-memory.md#6-a-prompt-rebuilt-at-every-decision), the memory note's options 7 and 6 | p50 2.7 s and p95 5.2 s under 20,000 tokens, against 9.0 s and 13.9 s over 150,000; confounded as stated above (S15) | The same model's first token: 4.11 s on a 1,000-token prompt, 5.23 s on 10,000, 9.45 s on 100,000 | With the cache kept, \$0.22 if every request cost what those under 60,000 tokens did. A 20,000-token prompt rebuilt at each decision loses the cache: \$0.83–1.03 (*arithmetic*) | Misses 2 s. It is the only recorded condition under which most responses were inside 5 s |
| **Effort setting:** the same model at low or no reasoning. The model accepts none, low, medium (the default), high, xhigh and max (S20) | Reasoning averages 44 of 127 output tokens; responses with none took p50 4.7 s (S15). A test on DeepSeek Flash 1017 with shortened context cut the median from 12.524 s to 1.415 s and did not separate the settings on grounding: 2 of 4 against 1 of 4 (S5) | Low: 2.76 s; 3.14 s. None: 2.20 s; 2.41 s | Same prices. Output is 3.3% of spend, so about \$0.78–0.80 if decisions per game hour do not change (*arithmetic*) | Misses. Not the main lever on this route |
| **Service tier:** the same model on Fast mode, the provider's priority tier | None | "up to 2.5× faster", stated for another model; prices are twice the standard rate (S20, S22). OpenRouter lists it at \$2.00 input and \$10.00 output per million for Terra and \$0.20 and \$1.00 for Luna (S19) | \$1.60 (*arithmetic*: twice \$0.80) | Misses even if the full multiplier applied: p95 3.2–5.5 s per actor (*arithmetic*) |
| **Smaller tier:** GPT-6 Luna ([#25](https://github.com/CVX-Hull/enactive/issues/25), whether a smaller tactical model earns its complexity) | None on the current interface | Medium: 6.26 s; 7.87 s. Low: 3.26 s; 4.44 s. None: 1.74 s; 2.32 s. Prices are a tenth of Terra's, cache reads a fifth (S18, S21) | About \$0.10 (*arithmetic*: the recorded token mix at Luna's prices, decisions unchanged) | Misses. At medium effort its first answer token comes later than Terra's on the mixed workloads |
| **Other provider:** DeepSeek V4.1 Flash 1017, the selected finite configuration (S14) | Medium on Fireworks US: medians 3.8–13.7 s over 56 requests (S5). Medium on BaseTen with 30 images: p50 11.8 s, p95 24.7–27.5 s (S13). No reasoning: median 1.415 s on shortened retained screens (S5) | No reasoning, the earlier listing of this model, median across providers: 0.90 s; 2.63 s. 48 endpoints from \$0.03 to \$0.60 input per million (S19) | About \$0.25 at the Fireworks US endpoint's prices (*arithmetic*; cache writes priced as input, because the endpoint lists no cache-write price) | Medium misses on both recorded providers. No reasoning was under 2 s only on shortened context |
| **Other provider:** Claude Haiku 5.5 | None on the current interface | Low: 6.99 s; 10.87 s. Medium: 11.03 s; 23.17 s. Prices equal Luna's up to 100,000 prompt tokens and are five times higher above (S19) | \$0.10–0.50 (*arithmetic*); the recorded median prompt is 93,828 tokens and the 90th percentile 197,459 (S6) | Misses |
| **Other provider:** Gemini 3.5 Flash-Lite | None on the current interface | 4.71 s; 11.61 s. \$0.30 input, \$2.50 output, \$0.03 cache read and \$0.083 cache write per million (S19) | About \$0.17–0.27 (*arithmetic*: cache writes at the listed \$0.083, or at the \$0.30 input price) | Misses |
| **Programs on the actor's interface** (the programs and monitor phase of [ADR 009](../decisions/009-curated-player.md#programs)) | A model-free step is a capture and an input: p95 392 ms and 58 ms (S3); an earlier local loop measured 362–379 ms per linked capture (S5). Use so far: one program in the current design, and no organic program run in any #164 recording (S8, line 51; S5) | Not applicable | Each decision moved to a model-free step removes about \$0.02 and 8 s. Supervising turns and model calls inside programs add cost back, unmeasured | The only option whose steps could fit inside 2 s and 500 ms; no program step has been timed in play. It applies only to decisions a program can take |
| **Required emissions and snapshot diffs** (ADR 009's [emissions](../decisions/009-curated-player.md#actor-emissions-d10) and [diffs](../decisions/009-curated-player.md#reaching-the-actor-without-latency-d2)): a cost, not a lever | One 200-token diff adds \$0.00106–0.00262, 5.5–13.5% of an average request (S6, lines 48–55). Emissions are unmeasured: the tool schema has no such fields and every sealed trace predates them | Not applicable | A 200-token diff on every request: \$0.04–0.11 more. Every 50 tokens of emission text per call: \$0.02–0.04 more (*arithmetic*) | Moves away from it: 50 more argument tokens take about 0.4–0.6 s at the recorded 80 to 130 tokens per second (*arithmetic*) |

## What the comparison shows

1. **Prompt size is the lever with recorded support,** and it is confounded. Responses
   under 20,000 tokens are 2.6 times quicker at the median than the lineage as a whole,
   and Artificial Analysis, a third party, shows the same direction for this model.
2. **Reasoning effort is not the main lever on this route.** The recorded responses
   carry little reasoning, and those with none are still over 4 s.
3. **No third-party figure shows any setting under 2 s on a prompt of this player's
   size.** On Artificial Analysis's 100,000-token workload the quickest first tokens are
   2.3–2.6 s, all with reasoning off; with reasoning on they run from 3.1 s to 23.2 s.
   The smaller tiers are cheaper, not quicker: Luna at medium effort is slower to its
   first answer token than Terra at medium.
4. **The one recorded test of turning reasoning off did not separate the settings.**
   Three cases with two repeats each: grounded replies were 2 of 4 at medium and 1 of 4
   with reasoning off, both settings missed the ration in the shelter menu, and no
   reply was both grounded and within 1.5 s (S5). The context was shortened, so its
   1.415 s median is not a figure for play.
5. **Pace moves cost per game hour as much as price does.** Across the priced options
   the *arithmetic* runs from about \$0.10 to \$1.60 per game hour. Within one lineage
   on one route, admissions ran from \$0.37 to \$6.61 per game hour. Fewer model
   decisions per game hour cuts cost on any route.
6. **A model call inside every counted decision cannot meet the criterion.** 1.6% of
   recorded responses finished within 2 s. A 2 s p95 over all decisions would need
   about 95% of them to be taken locally (*arithmetic*). Programs are the only option
   here that takes decisions locally, and none has yet run in play.

## Should the 2 s criterion stand?

**Recommendation: it stands as written. Add a per-request interval as a diagnostic that
every run reports, and define the 5 s stall so that an uncovered model wait counts.**

There are two readings of "new decision to visible effect". They differ in interval and
in population, and the second is easier to meet on both counts:

| | Frozen reading | Per-request reading |
| --- | --- | --- |
| Interval | From the first actor-visible cue sufficient for a new choice to the first capture that verifies its useful effect, with planning, tool handling, repair, retries and confirmation inside it (S5, cohort feasibility) | From the receipt of one capture to the receipt of the next request's first capture |
| Spans | As many requests as the decision takes | One request |
| Population | Useful routine decisions, judged from frames | Every request, setup and menus included |
| The shelter diagnostic | 22.169 s, one decision over three requests | Three intervals that sum to 22.169 s, about 7.4 s each; the first at least 11.6 s |
| The seven-day development lineage | Not measurable: no decision is labelled useful | p50 7.6 s, p95 12.9 s; 0.1% within 2 s (S15) |

Adopting the per-request reading as the criterion would be a change to it, not a way of
measuring it: a shorter interval, a wider population, and program steps counted where
the frozen text says "key/row/program counts do not". This note does not recommend
that. The reasons to keep the frozen reading:

- **The charter's rule is about the observer, and already allows a slow model.** "A
  slower model is acceptable only where useful execution covers its delay and the
  complete configuration still meets the declared cadence", with "loading and long
  activities separately visible and bounded" (S11). The criterion's own text says
  "Useful local execution may count." Shortening the interval to fit a model call would
  drop that rule; keeping it points the work at local execution.
- **The per-request interval already decides the question for now.** Every useful
  decision's interval holds at least one per-request interval. While 99.9% of those
  exceed 2 s, the frozen criterion cannot be met, and no labelling is needed to know
  it.
- **Route selection cannot reach it,** as the comparison shows. Held against the
  complete configuration, programs included, the criterion decides something.

What is added, as diagnostics and not as criteria:

1. **The per-request interval** on every run: its p50, p95 and the shares within 2 s
   and 5 s, split into response, dispatch and capture, with the actor's requests and
   any program's steps reported separately.
2. **The stall, defined.** A routine gap is time in which nothing useful is being
   executed for the observer. A wait for a model response counts toward it unless
   useful execution runs during the wait, the charter's "covers its delay". Nothing
   runs during a model wait today, so every response over 5 s is a stall: 79.5% of the
   seven-day development lineage's responses, setup and menus included (S15).
3. **Model response time** per actor trace, as now.

The frozen criterion still needs its own evidence before it can be met: 20 useful
decisions judged from frames by two reviewers. The feasibility pass put the chance of
collecting 20 from six sessions at 97.78% in its favourable scenario and 0.14% in its
middle one; both are sensitivity values, not measured rates (S12).

## Interaction with memory work

Owner premise (13 November 2026, recorded on #441, the parked seven-day screen:
[comment](https://github.com/CVX-Hull/enactive/issues/441#issuecomment-6854313488)):
memory is settled before any seven-day or other long run. Nothing here proposes a long
run. The [memory note](long-horizon-memory.md) of the same day recommends delivering
the player's own records in a working set, then an index of what is stored. Both add
prompt text and no model call per decision.

| Option | Interaction with memory work |
| --- | --- |
| Bound the context | The two works meet here. The memory note keeps a prompt rebuilt at each decision and compaction open as the ways to bound the context once memory works, not as the memory design; the trace evidence makes a bounded context the strongest cadence lever. Handing off earlier multiplies boundaries, and a handoff kept about 0.62 of what the outgoing actor held (memory note). A bounded context is only safe once memory carries what the conversation no longer does |
| Effort setting | Memory adds context to read on every decision. Whether an actor with little or no reasoning uses delivered memory is untested. The curator memory study scored traces of Terra at medium effort (S3, line 46; S4), so its results would not carry to another setting |
| Service tier | Independent of the memory design. It doubles the price of every token memory adds |
| Smaller tier | A second model. Replacing the actor leaves the memory evidence, all on Terra traces, without a subject. Beside the actor, the recorded cost of a curator on Terra is \$0.49 per game hour on the seven-day development lineage (S9, line 73), about five times a Luna actor's \$0.10 |
| Other provider | Cache pricing differs: DeepSeek endpoints list no cache-write price and cache implicitly (S19). The snapshot-diff estimate does not transfer to other routes (S6, lines 74–80) and would be measured again |
| Programs | The most dependent. In ADR 009 programs live in the knowledge repository, are induced, fitted and retired by the curator, and use the actor's expectations as success predicates (S8, lines 289–299 and 366–379). The curator and memory phase is not adopted and its study closed with a registered no-go (S8, lines 670–676); the memory note holds the curator until its first two options are measured. Who writes and curates programs is open until then |
| Emissions and diffs | These are memory's own cost to cadence: more output per decision and more prompt per request. A working set of 2,000 tokens is about 2% of the median prompt. Every figure above is for a prompt without them |

The consequence for order is this note's inference, not the owner's premise: memory will
change the prompt's size, its cache behaviour and possibly the number of models, so a
route measured now is measured on a prompt that is about to change.

## Proposed measurements

**The offline reading, done here at \$0.** The tables under
[What the sealed traces show](#what-the-sealed-traces-show) are its first result. What
remains is to make the script a tracked reader, extend it to the long-horizon arm and
the held-out lineage, and add the per-request interval to the run records. No model is
called. It needs no stop condition; it reads sealed evidence only.

**Retained-prompt replay probe, at most \$65.** It answers one question: on this
player's real prompts, which setting brings responses inside 5 s, and what does it cost
in grounding? Five seconds is #164's stall bound; 20.5% of recorded responses met it.

- **Inputs:** 20 decision points from the sealed seven-day development lineage, four
  from each prompt-size band of the table above, drawn by a seeded sample across its 14
  actors and frozen with their hashes before any call. No game runs and no tool call is
  executed.
- **Rebuilding the requests.** The host traces hold hashes of each request, not its
  body, and the repository has no replay tool; the host lists replay as unsupported.
  The probe needs an offline builder that reassembles each request from the package's
  prompt, the recorded tool calls and results and the session's original frames, and
  proves each rebuilt reference request against its recorded `payload_sha256`. That
  costs no dollars; it is estimated at one focused session with review. If the hashes
  cannot be reproduced, the probe does not run.
- **Settings, five:** the reference, Terra at medium effort on the default tier with
  the recorded prompt; the same with the history cut at a turn boundary to 20,000
  tokens; Terra with no reasoning; Terra on Fast mode; and Luna at medium effort.
- **Requests:** for each decision point and full-prompt setting, the actor's previous
  request once, to warm the provider cache as live play does, then the decision's own
  request twice. The cut prompt is sent twice with no warm-up. That is 280 requests,
  with no retries: a failed request is recorded as failed.
- **Measures:** time to headers, to the first tool-argument token and to completion;
  provider-reported cost; and the proposed tool call, rated grounded or not by two
  reviewers blind to the setting.
- **Cost:** about \$13 expected (*arithmetic*). Per decision point: a warm-up that
  writes about 89,000 tokens, the mean of the bands' medians, at \$1.25 per million is
  \$0.111, and two measured requests at the bands' mean recorded cost of \$0.0168 each
  bring a full-prompt setting to \$0.145. Fast mode doubles it, Luna is about a tenth
  (\$0.015), and the cut prompt is two uncached 20,000-token requests (\$0.05). That is
  \$0.645 per point. The worst case is \$60.85: every request a full cache write at the
  top of its band and every reply running to the 16,384-token output limit. Recorded
  replies averaged 127 tokens and never exceeded 1,051, so the \$65 stop is reachable
  only if a request is priced other than as listed or a response carries no cost
  record, which the spend-limit rule counts at \$0.4096.
- **Stop conditions:**
  - a pilot of one decision point through all five settings comes first; stop if the
    rebuilt reference request does not match its recorded hash, if a reply's prompt
    tokens differ from the recorded request's by more than 2% or its image count
    differs (the images did not reach the model), if any reply lacks its cost, usage or
    end-of-stream marker, or if it reports a model, provider or service tier other than
    the one requested (Fast mode can fall back to the default tier; S22);
  - stop at \$65 of provider-reported cost, counted per response as a player run's
    [spend limit](../operations/campaign-run.md#spend-limit) counts it;
  - decision points run in a seeded order that takes one from each prompt band in
    turn, so the two stops below see every band;
  - each reference replay is paired with its own recorded duration; stop after five
    decision points if the median ratio of replayed to recorded duration is outside 0.5
    to 2, because the replay then does not reproduce live serving. The factor of two is
    a judgment;
  - stop a setting other than the reference after eight decision points if none of its
    replies completed within 5 s.
- **Reading, fixed before it runs:** a setting is nominated for a later development run
  if the p95 of its 40 completions is at most 5 s and its grounded count is no more
  than four below the reference's of 40, with the paired difference and its interval,
  resampled by decision point, reported beside it. A setting that does not pass is
  recorded as not supported by this screen. Twenty prompts from one lineage can
  nominate a setting; they cannot qualify one or rule one out.

## Owner decisions

1. **The 2 s criterion.**
   - (a) It stands as written, with no added measurement.
   - (b) It stands as written, and every run reports the per-request interval and the
     stall as defined above, as diagnostics.
   - (c) Change it to the per-request interval over every routine request, p95 ≤ 2 s.
     This shortens the interval, widens the population and counts program steps.
   - (d) Change it by adding a looser bound for decisions the model takes, for example
     p95 ≤ 15 s, which the recorded 12.9 s would meet. This relaxes it.

   Recommendation: (b). Nothing is relaxed, and the diagnostic shows without labelling
   that the criterion is unmet.
2. **Order against memory work.**
   - (a) Change the route for cadence now.
   - (b) Settle memory first, as the owner's premise requires for long runs (S17), and
     hold route changes until the memory design has fixed the actor's context.

   Recommendation: (b). Holding route changes is this note's inference from the
   premise, not the premise itself.
3. **The route for development runs until then.**
   - (a) Keep GPT-6.1 Terra at medium effort on the default tier.
   - (b) Move it to Fast mode at twice the price.
   - (c) Move to GPT-6 Luna.
   - (d) Return to the selected DeepSeek configuration.
   - (e) Lower its effort.

   Recommendation: (a). It is the route every day-scale lineage and the memory evidence
   were recorded on. The traces show reasoning is a small part of its response time, so
   (e) is the weakest alternative.
4. **The context as the cadence lever.**
   - (a) Leave the context policy as it is: a 262,144-token window and 39 images.
   - (b) Treat a bounded context as the first cadence lever, and choose its form
     (earlier handoff, compaction or a rebuilt prompt) with the memory design, on a
     measurement.
   - (c) Lower the window now.

   Recommendation: (b). It has the only recorded support, it is confounded, and it
   loses play unless memory carries what the shorter conversation drops.
5. **The smaller tactical tier (#25).** Its revisit trigger has fired: the single-model
   route cannot meet its latency target (#25, state block of 7 November 2026).
   - (a) Adopt a smaller model as the actor.
   - (b) Reject a smaller tier.
   - (c) Defer it as the actor, and keep #25 as the place where small models are bound
     to the monitor and to model calls inside programs, each on recorded cases.

   Recommendation: (c). The figures of Artificial Analysis, a third party, show a
   smaller tier cheaper but not quicker with reasoning on, and nothing recorded shows
   it can play.
6. **Where #164 is qualified.**
   - (a) Against the route alone.
   - (b) Against the complete configuration once the programs and monitor phase exists,
     with program steps measured against 500 ms there.

   Recommendation: (b). Programs are the only option whose steps could fit the
   criteria.
7. **Budgets for emissions and snapshot diffs.**
   - (a) Carry the snapshot-diff note's caps, about 200 tokens per diff and 2,000 live
     (S6, lines 63–66), cap emission text at 50 tokens per call, and measure both in
     the first run that has them.
   - (b) Set no cap until they are measured.

   Recommendation: (a). Each is a direct, per-decision cost in time and money.
8. **The offline reading, \$0.** Make the script a tracked reader and extend it to the
   other sealed lineages, or leave it as this note's one-off.

   Recommendation: track it. It is how decision 1's diagnostic would be reported.
9. **The retained-prompt replay probe, at most \$65.**
   - (a) Do not run it.
   - (b) Run it now.
   - (c) Run it once the memory work has fixed the actor's context.

   Recommendation: (c). The probe replays prompts, and memory is about to change them.

## What this note cannot show

- **Published latency is not this player's latency.** The figures are averages of run
  medians on text prompts of about 1,000 to 100,000 tokens and on agentic tasks (S23).
  None is a 95th percentile, and none carries 39 images.
- **No provider page gives a latency number.** OpenAI's model pages state prices and
  effort settings only (S20, S21). OpenRouter's public endpoint list leaves its latency
  and throughput fields empty (S19). The latency figures are a third party's benchmark
  (S24), primary for its own measurements only.
- **How the benchmark was read.** Its figures were taken from the data embedded in each
  model page. The provider-comparison tables on the same site differ from them by up to
  about 1 s.
- **Not found in any source read:** a speed multiplier for Fast mode on GPT-6.1 Terra,
  a latency figure for the half-price flex tier that the endpoint list also offers
  (S19), and any figure for Claude Haiku 5.5 with reasoning off.
- **The trace reading is one lineage** of 1,978 requests on one route, played on
  7 November 2026, and its prompt-size effect is confounded as stated.
- **Every arithmetic cost assumes the recorded token mix and decisions per game hour.**
  A different model tokenises, reasons and plays differently; nothing here measures
  that.

## Sources

Line numbers are at commit `0e10e71`.

**Recorded in this repository**

| Key | Source |
| --- | --- |
| S1 | [Run ledger](../../data/evaluation/runs.jsonl): rows 31–37 (#382), 38–44 (#397) and 45–52 (#522), by the row's `study` field. `python -m tools.run_ledger totals --study ISSUE` reproduces attempts, wall seconds and spend |
| S2 | [Metrics snapshot](../../data/evaluation/run-metrics.jsonl): rows 31–37 (#382), 38–45 (#522) and 46–52 (#397), fields `decisions` and `survival.game_hours` |
| S3 | [Seven-day development lineage record](../acceptance/2026-11-07-seven-day-397.md): route, line 46; evaluator table, lines 121–129; lineage row, lines 132–136; input latency, lines 150–154; cost per day, lines 162–173; cadence table, lines 175–182 |
| S4 | [Long-horizon arm record](../acceptance/2026-11-07-long-horizon-382.md): lineage rows, lines 172–177, 218–226 and 264–267; arm result, lines 288–304 |
| S5 | [#164 iteration runs index](../acceptance/2026-11-04-issue164-runs.md), lines 28–32, and the published results it indexes: [cohort feasibility](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6623249182), [two-start calibration](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6637984197), [shelter diagnostic](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6638682260), [cadence readback](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6638915297) and [retained-screen test](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6639614118) |
| S6 | [Snapshot-diff cost](snapshot-diff-cost.md): lines 15, 25–26, 32–38, 48–55, 63–66 and 74–86 |
| S7 | [Development runs](../development-runs.md#benchmark): route, context and prices, lines 70–84 |
| S8 | [ADR 009](../decisions/009-curated-player.md): lines 51–56, 241–287, 289–379, 593–601 and 646–686 |
| S9 | [Curator shadow sessions record](../acceptance/2026-11-08-curator-shadow-454.md): results, lines 71–78 |
| S10 | [Evaluation contract](../contracts/evaluation.md): the stall event, line 121, and `stall.longest`, line 223 |
| S11 | [Charter](../charter.md): the responsiveness rule, lines 60–65 |
| S12 | [#164](https://github.com/CVX-Hull/enactive/issues/164), issue body read 13 November 2026: the first and third items under "Remaining qualification", the state block of 9 November 2026 and the cohort feasibility block of 4 November 2026 |
| S13 | [Observed effects record](../acceptance/2026-10-30-observed-effects.md): the BaseTen route and 30-image context, lines 36–37; complete response p50 and p95, line 164 |
| S14 | [Overview](../overview.md): the selected finite configuration, lines 34–35 |
| S15 | Sealed host traces of the seven-day development lineage: evidence study `397-seven-day`, `computer-sessions/*/actors/*/host.jsonl`, 14 traces ([evidence store](../operations/evidence-cleanup.md)), read 13 November 2026 by the method under [What the sealed traces show](#what-the-sealed-traces-show) |
| S16 | [Held-out lineage record](../acceptance/2026-11-09-held-out-lineage-522.md): size, line 89; spend, line 95 |
| S17 | Owner premise of 13 November 2026 on [#441](https://github.com/CVX-Hull/enactive/issues/441#issuecomment-6854313488), and the [memory note](long-horizon-memory.md) that rests on it |

**Published, retrieved 13 November 2026**

| Key | Title and address | Used for |
| --- | --- | --- |
| S18 | OpenRouter, public model list: <https://openrouter.ai/api/v1/models> | Prices per million tokens of every model named |
| S19 | OpenRouter, public endpoint lists: <https://openrouter.ai/api/v1/models/openai/gpt-6.1-terra/endpoints>, and the same address for `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash-1017`, `anthropic/claude-haiku-5.5` and `google/gemini-3.5-flash-lite` | Prices by provider and service tier; the long-prompt thresholds; the empty latency and throughput fields |
| S20 | OpenAI, "GPT-6.1 Terra": <https://developers.openai.com/api/docs/models/gpt-6.1-terra> | Effort values; \$1, \$0.05 and \$5 per million for input, cached input and output; cache writes \$1.25; Fast mode at twice the standard rate |
| S21 | OpenAI, "GPT-6 Luna": <https://developers.openai.com/api/docs/models/gpt-6-luna> | \$0.10, \$0.01 and \$0.50 per million; cache writes \$0.125; image input supported |
| S22 | OpenAI, "Fast mode": <https://developers.openai.com/api/docs/guides/fast-mode> | "up to 2.5× faster", stated for `gpt-5.6-sol`; the fall-back to the default tier |
| S23 | Artificial Analysis, "Language Model API Performance Benchmarking", version 3.0.0 of 3 November 2026: <https://artificialanalysis.ai/methodology/performance-benchmarking> | Definitions, workloads and averaging of the latency figures |
| S24 | Artificial Analysis model pages, each at <https://artificialanalysis.ai/models/> followed by its name: `gpt-6-1-terra-medium`, `gpt-6-1-terra-low`, `gpt-6-1-terra-non-reasoning`, `gpt-6-luna-medium`, `gpt-6-luna-low`, `gpt-6-luna-non-reasoning`, `deepseek-v4-1-flash-non-reasoning`, `gemini-3-5-flash-lite`, `claude-haiku-5-5-low` and `claude-haiku-5-5-medium` | Time to first answer token over all workloads, and time to first token on the 100,000-token workload |

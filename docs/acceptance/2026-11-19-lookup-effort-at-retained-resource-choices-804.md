---
owner: lead
status: historical
kind: review
date: '2026-11-19'
scope: 'Offline review of ordinary lookup effort at six retained resource choices from #803, #791 and #788'
---

# Ordinary lookup effort at retained resource choices (#804)

## At a glance

None of the six retained resource choices supports an efficiency comparison yet. Each case
has one executed branch, and no case shows the same cutoff with and without a lookup. Where
the historical player made an ordinary lookup, it took one or two tool calls. Per call,
tool time ran from 8.27 ms for a source read to 0.454 s for a menu call that also dropped
wood. Per turn, each model turn that issued a lookup took about 5 to 11 s and cost under
one cent; the one two-call lookup took 0.80 s of tool time and 17.1 s of model time. The 0.417 s baseline from #803 is
tool time only. The model turn that issued it took 5.0 s.

The second pass disagrees with the #803 record on one point. The ordinary item menu
showing both the matchbox and the matchbook first opened at request 104, not request 109.
That frame was still in the sent context when request 109 named the matchbox. In the
microwave case, rereading the captured frame would have left the yield unresolved: its
list is truncated. What the player inferred from it is not in the trace. The comparison still lacks one observation: a prospectively enrolled cutoff where
the target fact is missing from the sent context and from the action's own menu, with
both routes observed from that same cutoff. That is conclusion (b) below.

Offline development evidence only: no game, no model request, $0 spent.
[Joanna #803](2026-11-19-joanna-campground-memory-803.md) · [Retained review #791](2026-11-19-retained-memory-decision-791.md) · [Oceana #788](2026-11-19-oceana-farm-memory-788.md) · [Delayed-memory design](../design/delayed-memory-assessment.md)

## Method and terms

Source numbers are capture suffixes within the named admission. Each value is labelled as one of three kinds.
**Measured** means the historical run made the call. **Readback** means this review read a
sealed frame or trace now. **Hypothetical** means a call that was available but never made.

- **Tool time** is `latency_ms` from the maintained evaluator's `tool_calls` table, opened
  read-only. The tables are `joanna-campground-memory-803/operator/evaluations/8a4badef08b94ed78a8a031bf6751354/2-cdda-2.sqlite3`,
  `two-wake-memory-772/offline-evaluations/2bfa0eb2d8534a0a9df874625c1238cc/2-cdda-2.sqlite3`
  and `oceana-farm-memory-788/measurements/<session>/2-cdda-2.sqlite3`.
- **Model time, call counts, span wall time and reported cost** come from a one-off
  read-only script over each sealed `actors/001/host.jsonl`, not from a maintained reader.
  Model time is `response-complete.monotonic_ms` minus `request-start.monotonic_ms` for
  each player request, and tool time is `tool-result` minus `tool-start`, paired by
  `tool_call_id`. Wall time runs from the first `request-start` to the last `tool-result`.
  Cost is the sum of `reported_cost_usd` over player requests; recall requests inside
  a span are excluded.
- **Game clocks** are the evaluator's `game_time` readings in `steps`. A frame without its
  own reading is bracketed by the nearest steps that have one.
- **Sent-context state** (sent or omitted) is the exact manifest replay by `request_context`
  in `harness/evaluation/core/context.py`. For the player-host/7 Malvern trace, the
  sealed #791 `review/cutoffs.json` gives it instead.

The 64k packing results in #791 and #788 are a separate condition from the live route.
Nothing below uses them.

Scope: these six cases are the resource or equipment choices with ordinary access named in
the three records. Townsend swamp, Malvern cooking, Oceana pond, Oceana jar, the hearth and
the bathroom check were left out. They are a forage route, a recipe, a route, a placement
already on the current tile, or direct-action controls, so none has an ordinary lookup to
measure.

## Joanna matchbox (#803, opening admission, actor 001)

| Item | Evidence |
| --- | --- |
| Cutoff | Request 88, through line 1184 of the sealed `admission-1/actors/001/host.jsonl` (`operator/slot-01-request-88-before.json`). Clock 08:05:00, spring day 61 (source 2821). The matchbox fact is 5 game minutes old (pickup at 08:00, source 396). |
| Intent sent at cutoff | "Salvage picnic-bench wood to fuel a brazier." (request 88, line 1190). The matchbox was first named again at request 109 (line 1473): "Use the matchbox to ignite the fuel in the fire ring." |
| On screen | Source 2874: campfire hot dog recipe, "nearby fire" among the tools, 10 uncooked hot dogs. Source 2821: campground, 8:05:00 AM. |
| Sent context | Exact replay: 298 parts, 87 images, 60 omitted. Sources 394, 396, 1441 and 867 omitted (indexes 71, 74, 158, 118). Sources 2821 and 2874 sent. Sent tool-intent text keeps "Pick up the matchbox at Morgan's feet." and "Take the nine-match matchbox." (requests 23 and 24, trace lines 310 and 323). The matchbook is named in no trace text before the cutoff (readback search); only the omitted pixels of 1441 show it. |
| Handles | `player_source` was enabled (`actors/001/mcp.json`). The omitted sources 1441 (inventory: matchbook 20/20, matchbox 9/32) and 394 (matchbox 9/32) remained addressable. The inventory key and the item menu were both available. Actor 001 never called `player_source` in the whole trace. |
| Lookup measured | Yes, after the cutoff. Request 104 combined depositing the wood with opening the item menu, intent "Deposit the wood in the ring and select a match to light it." One call, 453.62 ms tool, 4.6 s model, $0.00429, source 3315. Request 109 opened the menu again: one call, 416.66 ms tool, 5.0 s model, $0.00448, source 3415. Both frames show matchbook (20/20) and matchbox (9/32). |
| Single normal lookup at cutoff | Readback: a `player_source` read of 1441 returns both containers and counts at about 08:02:41–08:02:46. Hypothetical at request 88. Its cost in this admission is unmeasured. A `player_source` call at request 88 would have been one more tool call. The ordinary item menu needed for either ignition shows both alternatives anyway, without a separate lookup. |
| Alternative | The carried full matchbook (20/20), shown in 1441, 3315 and 3415. |
| Span to effect | Requests 88–114: 27 requests and calls, 170.4 s model, 183.3 s wall, $0.18297. Requests 109–114: 6 requests, 37.1 s wall, $0.02674. |

## Whitethorn rod (#791, seven-day admission 5, request 19)

| Item | Evidence |
| --- | --- |
| Cutoff | Request 19 of `397-seven-day/computer-sessions/sd1a5/actors/001/host.jsonl`, `cutoff_wall` 2026-11-08T02:10:40.027Z (`retained-memory-decision-791/review/whitethorn-access.json`). No game clock is rendered in the prior or current frame, so the fact's game age is not established here. |
| Intent sent | The player-host/3 tool contract had no intent field. The request-19 action was two DOWN keys in the short-cordage recipe list (line 248). |
| On screen | Source 351: the short cordage recipe search. Prior source 3312 (admission 2): a basic fishing rod 7 tiles NW, "Owner: Your Followers". |
| Sent context | Per sealed #791 `cutoffs.json`, `whitethorn-rod`: prior pixels and omission handles both empty. The earlier source is absent from the prefix. |
| Handles | `player_memory_query`, `player_memory_read` and `player_source` were enabled (`sd1a5/actors/001/mcp.json`). Journal record `94ce47f3fff84a8ea69ea1a2dda03c74` held the rod location and source `507f7c538191fedb29b11639ed137b70-3312` before the cutoff (`whitethorn-access.json`). |
| Lookup measured | No. `observed_lookup_before_cutoff: false`. |
| Single normal lookup | Reconstructed by the earlier #791 record, not read again here: default query rank 5 and work-query rank 4, followed by a source read of 3312. That is two calls, hypothetical. Elsewhere in the same lineage, admissions 2–4 measured `player_memory_query` at 3.4–5.2 ms tool time and `player_source` at 5.3–6.0 ms. In admission 5, player model turns had a median of 7.3 s over 252 requests across both actors, and 4.85 s over the cutoff actor's 50 requests (one-off script). Current position, follower ownership and usability stay unverified. |
| Alternative | Prepare an improvised hook through the cordage recipes, which is the executed branch. Requests 19–24: 6 requests, 29.1 s wall, cost not reported in this trace version. |

## Malvern trunk (#791, two-wake admission 3, requests 287 and 288)

| Item | Evidence |
| --- | --- |
| Cutoff | Request 287 of `two-wake-memory-772/admission-3/actors/001/host.jsonl`. The current frame 13982 has no clock reading; it falls between day 63 02:27:37 (13879) and 02:28:38 (13996). Prior source 7401 falls between day 62 14:48:18 (7357) and 14:48:25 (7410). The fact is about 11 h 40 min old. |
| Intent sent | `player_source` on 7401: "Review the sedan trunk's other visible supplies for warmth materials." (line 3862). |
| On screen | Source 13982: the simple patchwork scarf recipe, cotton sheets missing, "too dark to craft". |
| Sent context | #791 `cutoffs.json`, `malvern-equipment`: prior pixels absent, one omission handle (index 485). After the lookup, at request 288, the pixels are present (index 884). |
| Lookup measured | Yes. One call, 8.27 ms tool (evaluator, the admission's only `player_source`), 6.6 s model, $0.00817. Readback of 7401: the sedan trunk holds a small fire extinguisher (10/10), a survival kit box with a glowstick and other items, and a toolbox. |
| Span to effect | Requests 287–302: 16 requests, 128.8 s model, 141.0 s wall, $0.14128. Pickup of the small fire extinguisher at day 63 02:28:58 (14333). The source read was under 0.1% of that tool time. The physical recovery took 15 more requests. |
| Alternative | Other warmth or shelter work at the current location, such as scarf crafting, which lacked cotton sheets. |

## Oceana grove cache (#788, admission 3)

| Item | Evidence |
| --- | --- |
| Cutoff | #788 names request 45, after the map lookup. This review reads the pre-lookup point as request 42. Frames 3257 and 3496 fall between day 62 04:44:50 and 04:45:00 (`measurements/9613db5a…/2-cdda-2.sqlite3`). The stick was crafted at day 62 04:21:16 (admission 2, source 6364), so the fact is about 24 minutes old. |
| Intent sent | Request 42: "Reassess the road and nearest mapped structures after moving away from the silo." Request 43: "Inspect the marked grove cache as a possible intermediate checkpoint." |
| Sent context | The predecessor report in `admission-3/actors/001/context.txt` (line 149) says the stick was left "at a marked grove cache". Earlier pixels are from another admission and were not in the prefix. Sources 3257, 3496 and 3633 were sent by request 45. |
| Lookup measured | Yes. Map open (request 42, 351 ms tool) and map navigation (request 43, 453 ms tool) are two calls: 17.1 s model, $0.00738 together. Source 3496 shows "Pointy stick cache". |
| Span to effect | Requests 42–74: 33 requests, 302.6 s wall, $0.18277, with one response unpriced. Source 6100 lists the long pointy stick 10 tiles W. 6121 shows 04:49:05. Pickup is unverified. |
| Alternative | Defer recovery. Source 6100 also lists sticks and long sticks nearby. |

## Oceana microwave (#788, admission 5, request 69)

| Item | Evidence |
| --- | --- |
| Cutoff | Request 69. Frame 3594, which that request returned, falls between day 63 04:00:06 and 04:01:55; a later reader reports that frame 3587, current at the cutoff, has the same bracket. Prior frames 938 and 939 were captured at requests 37–38, between day 62 17:11:32 and 17:11:42. The fact is about 10 h 49 min old. |
| Intent sent | "Select the farmhouse to recover a sheet of metal from its unused microwave." (line 929). |
| Sent context | Exact replay: 938 and 939 omitted (indexes 113 and 116). Brazier recipe 3507 and stable list 3587 sent. Earlier intents naming the microwave and "listed disassembly yield" (requests 35, 37 and 38) remain as sent text. |
| Lookup measured | No `player_source` before the trip. The executed route was map, travel, approach, disassemble and verify: requests 69–73, 5 requests, 36.2 s wall, $0.01997. Disassembly at day 63 04:46:50 (3932) recovered wires, scraps, converters, an amplifier, a motor and a magnetron. 3963 shows no sheet metal. |
| Single normal lookup | Readback of 939: the visible yield list is processor board, copper wire, electronic scraps, amplifier circuit, power converters, plastic chunks, micro electric motor and "and 1" before a scroll marker. Sheet metal does not appear in the visible part. A hypothetical one-call read would return that same truncated frame, so it could not settle the question. The open question was how to read the description at request 38, not the cost of a lookup. |
| Alternative | Search the current structure, or defer (`operator/slot-05-microwave-return-before.json`). |

## Oceana marked water (#788, admission 6, request 18)

| Item | Evidence |
| --- | --- |
| Cutoff | Request 18. Scene 398 falls between day 63 07:55:45 and 07:58:56. The note was made by admission 5, actor 002 (source 23654), between day 63 07:24:53 and 07:25:05, about 31–34 minutes earlier and across a Save/Load. |
| Intent sent | "Locate the previously marked water source using ordinary map notes." (line 245). |
| Sent context | Exact replay: 67 parts, 0 omitted images, 398 sent. The report in `admission-6/actors/001/context.txt` (line 151) states that a murky-water tile was seen "with an approximate map note". |
| Lookup measured | Yes. One call, ESC, m, Shift+L, 403 ms tool, 5.2 s model, $0.00265. Source 401 lists "Murky water NW nearby", distance 13, under "Pointy stick cache". |
| Span to effect | Requests 18–28: 11 requests, 67.9 s wall, $0.03242. The jar was filled with murky water at day 63 08:04:10 (1170). |
| Alternative | Continue nearby foraging, or defer while hydrated (`operator/slot-06-marked-water-before.json`). |

## Verification of branch and scored effect

This second pass reread the executed branch from the trace and frames, apart from the
reconstruction above.

- **Joanna: disagreement with the #803 record.** The record says request 109 stated the
  matchbox intent before opening the ordinary item menu, and that this single call took
  0.417 s. Both statements are literally true of request 109. However, request 104 had
  already opened the same "Use item" menu (453.62 ms, source 3315). Source 3315 shows
  matchbook 20/20 and matchbox 9/32, with "You drop your splintered wood on the grass. x 2".
  Exact replay shows 3315 was sent at index 342 in the request-109 context. The
  matchbox intent therefore followed a visible two-choice menu: request 109 was the second
  menu opening, not the first. Ignition was rereadable: 3805 shows "You successfully light
  a fire." at 8:10:58 AM, spring day 61, with the avatar unnamed. 4493 shows matchbox 8/32,
  matchbook 20/20 and the hot dog craft at 3%. This agrees with the record.
- **Joanna name window:** only 3805 and 4493 were viewed. The other frames of the
  five-operation window (3877, 3878, 3986, 4137, 4277) were not; see below.
- **Malvern:** agrees with #791. The pickup at 02:28:58 is visible in 14333. No name
  appears in that frame. Later frames were not reread.
- **Whitethorn, grove, microwave, marked water:** the branches and frames above agree with
  #791 and #788. Grove pickup and named effect remain unverified, as both records say.
  No case scores a named effect in its window.

## Measured, readback and hypothetical

| Case | Measured historical lookup | Offline readback now | Hypothetical access |
| --- | --- | --- | --- |
| Joanna | Item menu twice: 453.62 ms (104) and 416.66 ms (109) | 1441 and 3315 show both containers | Source read of 1441 at request 88 |
| Whitethorn | None | None; query rank 5 or 4 is the earlier #791 record's reconstruction | Query plus source read |
| Malvern | Source read of 7401, 8.27 ms | 7401 contents | None |
| Grove | Map note view, 351 + 453 ms | 3496 note | None |
| Microwave | None | 939 truncated yield, no sheet metal visible | Source read of 939 |
| Marked water | Notes list, 403 ms | 401 note at distance 13 | None |

An available handle does not establish its cost, a successful retrieval or a memory
advantage. Tool times above come from different routes and frame sizes and are not
matched.

## Conclusion: (b) the evidence still missing

The retained evidence cannot settle a comparison design. None of the six cases observes
two routes from the same cutoff. In Joanna the required action menu already shows the
alternatives. In Malvern, the grove and the marked water, the measured lookup was cheap
but was the route actually taken. In Whitethorn and the microwave no lookup was made, and
the microwave's one candidate frame is truncated.

The smallest settling observation is one prospectively enrolled cutoff in ordinary play
that meets all of the following:

- the target fact is absent from the sent context, and the action's own menu does not
  display it;
- an ordinary handle such as a source ID, map note or journal record exists before the
  cutoff;
- the same cutoff is observed under both routes, a lookup and a re-observation or trip,
  by paired replay or a matched second admission.

Malvern meets the first two conditions, taking "the action's own menu" as the menu
available at the cutoff before any travel, and shows why the third is the missing one: the
lookup was made and walking to the trunk was feasible, but only one route was observed.

Record the lookup calls, tool time and model time, plus the requests, wall time and
reported cost to the effect, and the named effect. The proposed effort unit for a later
design is player requests from cutoff to verified effect, with model seconds and reported
dollars beside it.

The retained spans give scale only, not estimates of a difference: 5 to 33 requests,
29 to 303 s of wall time, and $0.020 to $0.183 where a cost was reported. A lookup's own
tool time (8 ms to 0.45 s per call) is negligible beside its model turn (4.6 to 10.8 s
per turn). Tool latency alone is the wrong unit,
including the 0.417 s baseline. Any new acquisition or paired replay needs its own priced
decision.

## Not established in this pass

- Whitethorn: the game age of the rod fact, and the rod's state at the cutoff.
- Microwave: whether a scrolled description at request 38 would have listed sheet metal.
  It was not captured.
- None of the tool-time comparisons across cases is matched for route, frame size or host
  version.

## Separate reader

A second reader, working from the sealed store without the first pass's scripts,
recomputed the measured figures in the six tables with its own script over each
`host.jsonl`, its own replay of the context manifests and the evaluator databases, and
opened 30 frames. The Whitethorn query ranks are carried from the #791 record and were
not recomputed. The figures matched except those corrected above: the model-time range,
one `player_source` latency taken from a later admission, one label, the wall-time range
and the pooled median. It confirmed three points where this review adds to or differs
from the earlier records: the item menu already open at request 104 in #803, the grove
cutoff falling after its map lookup, and the truncated microwave frame.

It also read the frames the first pass had not: Joanna 3877, 3878, 3986, 4137, 4277,
4452 and 4456, and every Malvern source from 14334 to 14616. No living survivor's name
is visible in any of them. Joanna 4453 was not opened.

The grove case's request 45 appears in #788 only as a cutoff point in its 64k packing
table; this review uses the cutoff and none of the packing results.

## Limits

All six cases are inspected development evidence from four lineages, with the Oceana cases
sharing one world group. They support no comparison or generalization claim. This review
used no reserved world. It did not rescore or relabel any past result. Model times,
spans and costs come from a one-off read-only script by the stated method. Re-running it
over the cited `host.jsonl` lines reproduces them.

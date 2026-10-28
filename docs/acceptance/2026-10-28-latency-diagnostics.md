---
owner: lead
review_trigger: Endpoint selection, diagnostic format or latency interpretation changes
status: historical
date: 2026-10-28
scope: Retained Pi host diagnostics and public endpoint research; no new paid inference or native gameplay
---

# Retained latency evidence and endpoint selection

Observed October 28, 2026 under [#280](https://github.com/CVX-Hull/enactive/issues/280),
with useful apparent latency still owned by [#164](https://github.com/CVX-Hull/enactive/issues/164).
The owner requested better telemetry, analysis of retained data and provider-neutral
speed research while gameplay remained paused. No paid request, credential access,
native admission or provider switch was performed for this follow-up.

## Findings that change the next experiment

Model-request intervals dominate recent host elapsed time. Faster serving and less
unproductive generation deserve priority, alongside player-authored programs that
produce useful effects locally. Neither HTTP completion nor program termination
establishes useful progress. Prior failed selection/phase handling remains a quality
constraint: making the same mistake faster is insufficient.

Lower effort has already been tried. Ten recognized low-effort hosts have response
medians of 6.499–8.566 s. Their conditions differ from the 30 medium-effort hosts (response
medians of 6.211–25.508 s among 29 hosts with uncensored completions). This observational
range is **not an effort ablation**: sources, briefs, output caps, task difficulty,
recovery and endings changed. [Program-breadth007/008](2026-10-25-program-breadth.md#007-normal-ending-no-useful-program-effect)
ended normally at low effort but missed useful program effects through concrete
selection/precondition errors. The later medium episodes also have successes and
failures. Reuse those retained failure scenes when screening another configuration;
do not repeat low effort as though it were untried or treat medium as inherently
required.

## Corpus and reproducibility

`tools.evaluate host-summary .runtime/campaigns` inventories 171 selected trace files:
40 recognized Pi hosts, 48 empty placeholders and 83 unsupported historical formats;
zero invalid or duplicate-full-content traces in this snapshot. All 40 declare the
same version-pinned `deepseek-ai/DeepSeek-V4.1-Flash-1017:zRTkTPfs`; each has retained
frozen source and model settings. These are host observations, not 171 independent
gameplay experiments, unique global HTTP transactions or a billing ledger. Empty
successors provide no experiment result. Unsupported legacy formats are listed but
not semantically analyzed; this does not claim exhaustive analysis of all runtime
files or manufacture a compatibility reader.

The source-only analysis adds compact per-request rows, reported usage coverage,
censoring, request/tool interval unions, declared source/configuration and optional
stream/logging diagnostics. No averages are pooled across changed experiments.
Coverage and unsupported input remain visible; missing old diagnostics cannot be
backfilled. Full derived JSON and the endpoint metadata snapshot remain private in
`.runtime/telemetry-analysis-20261028/`; run the documented
[evaluator commands](../evaluation.md#retained-host-and-browser-analysis) to regenerate
from retained inputs. Existing historical outcome assessments remain necessary to
interpret usefulness; a host reporting `completed` can still have failed its mission.

Selected recent diagnostics, seconds unless shown otherwise:

| Host | Request share of host time | Median complete response | Median tool | Median output/post-body proxy, tokens/s |
| --- | ---: | ---: | ---: | ---: |
| context001 original, standard |94.93%|9.717|0.458|76.2|
| context004 original, priority |97.12%|22.326|0.369|73.6|
| context004 successor, priority |99.77%|20.252|0.009|47.1|
| context005 original, interrupted |97.65%|15.387|0.445|68.2|

Shares include observed canceled intervals and client-side request work; only
uncensored `stop`/`toolUse` responses enter response medians. They do not isolate
server inference, network, provider queuing or logging. Individual tools still
have tails: the selected original hosts each contain an approximately 15 s tool.
Priority and standard ran different tasks/history/source conditions; the table
establishes no causal tier improvement or regression.

For the same selected hosts, median headers arrive in 1.13–1.44 s and first body
in 2.21–3.50 s. Reported reasoning is 69–80% of their reported output tokens, already
included in output rather than added again. The successor's longest response is
229.486 s with 7,318 output tokens, including 6,920 reasoning tokens. The empirical
output/post-first-body rate varies with startup, buffering, reasoning and usage
semantics; it is not a server decoder clock. Long generation and quality/correction
work are credible targets, while the new stream endpoints are needed to distinguish
first semantic progress, stalls and final response latency prospectively.

An exact retained metadata join for context004 finds 72 distinct frame/capture DOM
witnesses (median 118 ms, p95 291 ms, max 821 ms), with 60 unmatched source rows. Export
retention dropped 56,488 status records and zero frame records. The selected actual
knife-wield frame reproduces 134 ms capture→DOM. The earlier explicit-intention and
prior-result exposure proxies to that selected DOM were 173.961 s and 207.128 s.
These are selected proxies, not earliest attention or physical paint; aggregate
frame speed cannot qualify whole useful decisions. The join checks current frame
identity, geometry and capture epochs, not PNG integrity or current applicability.
context005 remains owner-censored, and004 lacks a useful admitted successor and
normal ending. No responsiveness/readiness pass follows.

## Current endpoint evidence

Primary pages and public endpoint metadata were retrieved October 28, 2026; live
measurements change. The [model's official release note](https://api-docs.deepseek.com/news/news261017/)
claims shorter outputs and faster task completion than its predecessor, without a
numeric serving SLA. Our actual pinned route and reasoning configuration remain
the comparison baseline, rather than replacing them with the newest model alias.

[Artificial Analysis's own provider measurements](https://artificialanalysis.ai/models/deepseek-v4-1-flash-1017/providers)
show the following snapshot for **1017 Max**, default 10k-input workload, P50 over
72 hours. Output speed starts after first chunk; first answer includes reasoning.
The total-response estimate uses 500 answer tokens and average thinking from 60 prompts.

| Endpoint label | Output tokens/s | First chunk, s | Estimated total response, s |
| --- | ---: | ---: | ---: |
| DeepInfra |65|0.69|39.18|
| DeepSeek |184|1.17|14.78|
| Fireworks |203|1.48|13.80|
| Baseten regular |265|0.28|9.70|
| Baseten FAST |882|0.20|3.04|

These establish promising serving alternatives, not expected CDDA results. Our
recent original-host 68–76 tokens/s streaming proxies are broadly compatible with the slower
endpoint's scale, despite different workload/effort/measurement. Max benchmarks
cannot predict medium gameplay response distributions. FAST variants, quantization,
vision, exact snapshot, tool serialization, cache warmth and availability need
separate qualification; no numeric speed guarantee or quality equivalence follows.

The [public OpenRouter endpoint API](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints)
snapshot at 23:37:33 UTC lists 39 endpoints, including exact DeepInfra standard/flex/
priority tags, DeepSeek, Fireworks and Baseten. Model-level modalities are text+
image; per-endpoint lists declare tools and reasoning effort. All 30-minute throughput
and latency fields were null. Baseten's listed tag is `baseten`, with unknown
quantization; it does not identify the separate benchmark FAST variant. Metadata
advertisement is not an actual vision/tool/effort conformance test. Do not substitute
an earlier dynamic provider-grid screenshot or invented endpoint rate for missing
measurements.

[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection)
can pin a full endpoint slug, disable fallback and require supported parameters.
Throughput sorting and latency preferences are selection aids, not guarantees.
A router selecting DeepInfra retains that backend; changing the router alone does
not demonstrate faster serving. [Caching behavior](https://openrouter.ai/docs/guides/best-practices/prompt-caching)
includes sticky routing, with explicit provider order overriding automatic stickiness.
Compare cold and warmed contexts, preserve the stable prefix, record actual cache
usage and route, and expose upstream attempts before interpreting results.

Effort labels also need conformance. [DeepSeek's own API](https://api-docs.deepseek.com/guides/thinking_mode/)
maps requested `medium` to actual `high`, with thinking enabled/high by default;
its explicit thinking toggle is distinct from effort. This does **not** attest
DeepInfra or OpenRouter semantics. [DeepInfra's general reasoning guide](https://docs.deepinfra.com/chat/reasoning)
describes `reasoning_effort:none` for disabling reasoning, but the selected pinned
model needs verification. Pi's frozen mapping describes what we send, not what a
backend actually executes. Omitting a field is not proof of disabled reasoning.

## Next bounded iteration

Recommend an approximately 8 active-hour iteration, with most experiment time spent
on organic play and outcome review. GitHub owns the selected scope/resources;
this recommendation neither resumes play nor grants a new frozen native admission.

1. Deliver the reviewed telemetry/analysis source with the existing host fixes in
   one consolidated delivery. Add only the necessary route/credential admission
   seam: the generic host is configurable, but the campaign launcher still assumes
   `DEEPINFRA_API_KEY`. A new provider must receive its own correctly scoped key.
2. Refresh exact endpoint availability and shortlist two materially faster serving
   candidates, irrespective of vendor: prioritize a qualified Baseten FAST route
   if available, otherwise the advertised regular route/Fireworks; compare direct
   DeepSeek where its exact vision/tool interface fits. OpenRouter is a convenient
   fixed-endpoint candidate path, not the acceptance target.
3. Perform a small retained-scene conformance screen with current screenshots,
   complete tool schemas and known007/008/context004 failure decisions. Separate
   route speed from reasoning changes; record effort/output cap, actual backend,
   cold/warm cache, first semantic data, completion, failures and output validity.
   Stop only configurations that fail to read/act through the required interfaces;
   a screen pass establishes eligibility, not gameplay quality.
4. Put the most promising eligible configuration into bounded organic gameplay
   early. Keep the current baseline as reference; freeze useful decisions before
   play, retain all correction chains/failed tasks and separately measure local
   program effects. Use the existing 20-decision requirement for formal cadence;
   insufficient natural samples stay inconclusive, without filler or task splitting.
   Include useful progress and proper ending/succession when in scope.
5. Analyze the complete run, rank useful success and apparent latency including
   repair costs, and consolidate findings/fixes in the same delivery. Budget roughly
   1 h integration, 1 h endpoint/conformance work, 4 h play/assessment and 2 h analysis/review;
   revise from observations rather than spending the iteration on synthetic tests.

[#281](https://github.com/CVX-Hull/enactive/issues/281) remains the separate measured
archive-growth follow-up. It should not distract from the dominant request-time
path unless actual stage measurements change that ranking. No new dashboard,
telemetry store, broker or model hierarchy is justified by this evidence.

## Verification and delivery limits

The full actual Pi SDK/MCP/CLI package passed110 tests in45.87s; focused stream
checks passed again after the final metadata snapshot adjustment. Offline analyzer
and existing evaluation tests passed32 tests. Fast repository checks passed after
correcting required report metadata. Independent source review found and verified
repairs for unknown completion reasons, missing endpoints, malformed shapes,
unsupported versions and negative clock evidence; a separate evidence review
matched the selected statistics, historical outcomes and primary-source table.

These are source/fixture and retained-data checks. New diagnostics have not yet
been measured during live gameplay; logging overhead remains part of the next
measurement. Consolidated protected CI/full-regression delivery is pending, as is
#280's broader native outcome. No existing failed or interrupted run is relabelled.

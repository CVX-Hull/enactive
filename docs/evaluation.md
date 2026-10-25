---
owner: maintainer
review_trigger: Evaluation schema, caller, scenario protocol or accounting changes
status: active
---

# Record and review gameplay measurements

The passive recorder measures explicitly supplied observations; it does not run
the game, call a model or judge success. Future planner/skill adapters must record
their actual calls and outcomes. Closed Codex host traces now supply scoped
response-token and tool-call/gap evidence; isolated inference, hidden approval
telemetry and full event-to-useful-effect latency remain unavailable where not
explicitly instrumented. An empty call list does not establish zero total cost.

The [passive supervisor](protocol.md#passive-waypoint-supervision) exposes bounded
action/decision events and the original planner port's accounting snapshot. Merge
one snapshot at the chosen cutoff, then record its events once in elapsed-time
order. The caller and independent assessor still supply manifest, final outcome,
usefulness and harm judgments. Fixture events must remain labeled synthetic;
an eligible intent never proves native dispatch or model effectiveness.

The [round brief](changes/007-recovery-evaluation-monitoring.md#waypoint-experiment-protocol)
owns the predeclared waypoint families, development/held-out split, repeats,
budgets and pilot decision thresholds for #24. No live model comparison is claimed
by this tooling. Change that protocol before collecting affected outcomes, with a
recorded reason; do not tune thresholds after seeing results.

## Pi host events

The optional [Pi host](components/player-interface.md) writes JSONL into the
driver's existing `driver-<role>.jsonl`. Each event has `wall_time` and
`monotonic_ms`; request and tool IDs correlate host phases, while complete tool
results retain the existing mission operation/source references. The host does
not create another mission ledger or treat a JSON-RPC ID as durable operation
identity. Missing clock joins remain unknown.

| Event | Observation and limit |
| --- | --- |
| `host-start`, `mcp-connected` | Frozen route/effort, unsupported features, missing endpoints and owned MCP PID; not actual provider/model competence or game authority. |
| `request-start` | Constructed provider payload sizes, text/image counts and host request identity; begins at the selected SDK request boundary, not the user's decision or server inference. |
| `response-headers`, `response-first-chunk` | HTTP status and first received response-body chunk observed locally; either can precede useful content and neither timestamp isolates queue/inference time. |
| `response-backend` | Model identifier reported by a parsed provider event; an absent or alias-only identifier does not establish an immutable backend version. |
| `response-complete` | Completed SDK response's stop reason and returned usage/model metadata; successful response receipt is not successful gameplay. Missing input/output counts mean `usage_available:false`, `usage:null` and unknown cost. Reported counts enable normalized usage; `cost_source` distinguishes provider totals from configured-rate estimates. |
| `tool-start`, `tool-result` | Actual MCP call arguments and complete returned text/image/error envelope; retain original collection on uncertainty. This is tool service/transport evidence, not native effect or physical display. |
| `tool-refused` | A zero-dispatch argument-normalization refusal; the model may make an explicit corrected call, without software repairing its original selection. |
| `abort`, `settled` | Host stop reason, request count and cleanup disposition. `native_cleanup_claimed:false` remains explicit; prompt resolution or an event alone does not qualify normal game ending. |

The raw provider headers, keys and arbitrary provider error text are not retained.
There is no automatic compaction in this core host; its absence is disclosed at
startup rather than measured as a hidden model service. Finite request/host bounds
and context/provider errors stop without pruning or fallback. Offline synthetic
SSE/MCP probes exercise the real SDK and serialization but perform no inference
or gameplay. Their elapsed/instrumentation measurements are fixture-only costs.
Live useful-effect/cadence criteria and all-role costs remain unchanged below;
[#236](https://github.com/CVX-Hull/enactive/issues/236) owns any matched comparison.

## Latency budgets for interactive play

The [responsive-player brief](changes/060-responsive-player.md) records the latest
closed-host diagnosis, proposed initial numerical targets and configuration
admission experiment. [S-UX](engineering.md#s-ux-understandable-and-controllable-experience)
requires prospective cadence/quality criteria for new responsiveness claims;
the slow current arrangement is not qualified. New requirements do not rewrite
a frozen deciding run's acceptance. A functional run can remain useful evidence
while failing to qualify responsiveness.

Freeze both the qualification decision and development stopping policy. An
uninstrumented interval or fewer than the required useful decisions establishes
no percentile pass; a measured miss rejects the configuration. Neither alone
requires an otherwise eligible, finite development run to end. Continue only
within the original coupled forecast, ending deadline and authority/delivery
constraints under the [development workflow](project-management.md#minimum-checks-and-escalation).
Retain acquisition, repair, slow intervals and failures in total costs. Do not
relax the numerical targets, retrospectively alter a frozen brief or call a
seven-day functional result a responsive service without the required evidence.

Native input, skill execution, observer presentation and player reasoning have
separate clocks. A timeout is a ceiling, not a fixed delay: return immediately
when the matching acknowledgement arrives. Use one higher-level player decision
for a bounded semantic skill; the controller observes and guards its primitives
without a model or approval round trip per key. Retrieve memory at meaningful
planning/correction/handoff boundaries, not automatically for every primitive.

Qualification 004's 31 returned primitives had a 62.33 ms median, 91.30 ms nearest-rank
p95 and 95.37 ms maximum **retained preflight-to-ACK interval**. This includes host
callback/persistence, native input/frame and transport; it is not pure engine or
end-to-end player latency. Its world-selection ready ACK arrived 7.272 seconds after
journaled admission, outside the default 5-second wait. The matching acknowledgement
remains historical; an explicit 15-second setting was chosen prospectively for later
attempts, within the existing controller limit. Neither changing a ceiling nor
fast ordinary samples resolves an old unknown or measures all loading cases.

[Qualification006](acceptance/2026-10-20-native-character-lifecycle.md) broadens the
sample: 66 ordinary returned inputs, excluding world entry, had 120.96 ms median,
242.11 ms nearest-rank p95 and 508.84 ms maximum. All 67 returns had 242.78 ms p95;
world entry took 7580.40 ms. UI categories and sample sizes differ from 004, so this
is not a controlled regression or speedup comparison. No movement was delivered.
One 15-primitive name batch reached its last receipt in 1.886 seconds, and eight
inventory arrows in 2.779 seconds from admission. Those are **last-receipt proxies**,
not settled-result timestamps; model/tool/approval and actual browser decode
latency remain unknown. Three session/exit ACK timeouts are separate from those
successful intervals. Whole engineering wall time includes investigation and
cannot be used as player or engine throughput.

[Qualification007](acceptance/2026-10-20-native-lifecycle-qualified.md) has106returned
inputs: median101.72ms, nearest-rank p95337.46ms, maximum6716.55ms. Excluding the
preselected world-entry input leaves105: median100.50ms, p95336.68ms and
maximum856.24ms. Its four movement steps span156.61–191.63ms (median182.00ms,
nearest-rank p95=maximum); this is too small a sample for a general claim. A
known two-step return reached its last receipt767.54ms after admission, a20key
world-name batch2173ms, and eight inventory-focus arrows4293ms. Those are
last-receipt proxies; an interpreted-result terminal timestamp is unavailable.
Six unknown ACKs remain separate, with effects reconciled. Whole1941.5second
engineering wall time includes unmeasured planning/tool work and is not throughput.
The broader ordinary p95 exceeds the proposed250ms target. Profile the tails and
model/tool/display boundaries before choosing faster models or adding infrastructure.

[Native008](acceptance/2026-10-20-confirmation-correction.md) adds 64 returned
setup/menu/identity intervals: median 77.91 ms, nearest-rank p95 141.60 ms and
maximum 6393.12 ms, with three unknown ACKs retained separately. This is another
scope/sample, not a controlled improvement over007. Its 517.49-second deliberate
qualification does not measure normal-play throughput, model or browser latency.

| Proposed next-campaign target | Measurement / limit |
| --- | --- |
| Ordinary movement/menu input p95 ≤250 ms | Original retained preflight-to-terminal ACK intervals; report sample count, rejected/unknown inputs and tails separately |
| Newly available frame displayed within 500 ms during active play | Native frame/capture to successful browser decode; the active poll now schedules 250 ms after the preceding status response, idle/disconnected 1000 ms. Cadence alone does not prove the target |
| Small semantic batches complete within a few seconds | Whole request admission to settled outcome; report primitive count and model/approval/tool overhead separately. A 20-key edit's native intervals target ≤5 seconds |
| Player makes goal/outcome decisions, rather than decisions per key | Compare actual decision boundaries and skill requests; requests are not automatically model-call counts |
| Loading and long activities have separate finite budgets | Record visible readiness/progress and actual stop/unknowns; do not apply the 250 ms input target or treat a 15-second wait as a universal load guarantee |

These remain proposed component targets, not passing badges or requirements for
optional model tiers, telemetry frameworks or paid providers. Configuration
admission also needs useful-progress/stall and quality criteria frozen before its
experiment. The existing native journals/ledger/archive, closed host traces and
viewer provide the starting evidence; isolated model time, hidden approval delay
and complete tool-to-visible-effect cost remain unmeasured where not correlated. #143 owns
observer latency, #154 integrated timing evidence and #156 prospective setup;
#145 uses actual mission results before a full campaign. Existing S-UX/S-EVIDENCE
and native acceptance enforce honest evidence; common tests do not enforce wall
percentiles. Revisit targets after representative navigation/items/activities and
fresh-context player measurements, retaining both tails and failures. Reuse CDDA
travel/activities where qualified before adding an execution framework.

[Fresh019's closed program trace](acceptance/2026-10-24-independent-seven-day-nineteenth-attempt.md#cost-and-responsiveness-evidence)
separates selected-capture-to-root admission (median7.742s, eight roots) from
within-program returned-normal capture intervals (median520.5ms,42pairs) and V8
execution (median0.880ms,58evaluations). These are selected same-host proxies,
not isolated inference, useful-task/display latency or a causal comparison.
Measure whether player-authored routines amortize decision gaps across useful
outcomes while retaining organic surprise/correction, not merely fast evaluation.

The next bounded measurement should correlate existing request/dispatch IDs across
admission, bridge publication, terminal receipt, semantic settlement, status
response and successful image decode. Use monotonic intervals within each process;
browser/server clocks need explicit correlation before subtraction. The controller's
15 ms receipt polling and viewer's active 250 ms post-response poll are hypotheses
to profile, not explanations for all delay. Prioritize removing per-key player/tool
round trips and unnecessary captures or repeated retrieval. Keep per-primitive
outcome/authority checks; batch decisions rather than blindly batching input.
Do not add a broker, telemetry service or new model tier without an observed gap.

### Request settlement clocks

The existing controller journal records `mission_request_settled` with a
`mission-timing/1` outcome for each original admitted semantic work item, and for
an explicitly certified no-admission refusal. Cached collection and passive reads
add no duplicate settlement. The row carries mission/request/epoch/controller-boot
identity, original ledger admission wall time, process-monotonic receipt/admission/
settlement endpoints, observed row state, writer-finalization status, mission
phase, censoring and available source reference. No request body/image is copied.

Receipt is runtime work-handle creation; admission clocks bracket `begin_request`;
settlement ends after that invocation's post-commit lifecycle/reflection work and
per-work finally publication/handle cleanup, before timing append overhead. Atomic
handoff/claim/Observe and Finish share this hook. A completed request row is not
proof of terminal mission success: Finish may retain its report while withholding
terminal persistence. Unknown/canceled/failed outcomes retain their actual state;
missing events do not imply zero cost or no admission.

`request_timing_summary` in the existing passive evaluation module projects the
same-boot runtime, queue, admission and post-admission service intervals. Supply
expected durable request IDs to expose absent endpoints. Duplicate settlements
are censored; missing/invalid clocks and observed wall regression remain explicit.
Wall correspondence is otherwise unassessed. The wall anchor is bracketed by two
monotonic samples; do not subtract unrelated process/host clocks or assume a
constant wall offset. Source/frame joins still need their exact retained records.

These machine-only events are excluded from recent status/UI and default player
context. The existing journal writer is reused, with no per-primitive event,
second store or timing service. A timing-only append failure is logged as a
missing sample without changing the committed operation; required domain
persistence failures retain their guards. Measure append overhead separately.
This addition does not retrospectively fill Fresh024's missing endpoints, identify
model inference, establish physical paint or qualify useful whole-player cadence.

For the next assessment, freeze the useful-decision cohort before play under the
linked responsiveness criteria. Members are independently meaningful, source-backed
goal/outcome choices in familiar normal play; keys, procedure invocations and
program termination are not automatically members. A correction chain retains
the original decision's start and all repair costs through verified useful effect.
Loading, long activities and novel deliberation have separately declared finite
cohorts; none disappears from whole-run accounting. Missing endpoints or too few
evaluable useful decisions cannot produce a percentile pass. Do not manufacture
extra decisions by splitting a journey or replaying filler actions.

Use an actual sufficient-evidence receipt as the start where available. Otherwise
a matched selected capture may provide a conservative earlier start only under
the explicitly checked same-host clock/identity assumptions; label that proxy and
its uncertainty. A matched successful browser decode is a declared display proxy,
not physical paint. New service clocks separate software work from arrival gaps;
they do not turn those gaps into inference measurements. Source/operation/frame
joins are automatic; the independent assessor judges usefulness from retained
intent/effects, without asking the player for per-key annotations or curating play.

The current local spectator snapshot/export is `observer-timing/3`; historical v1/v2 captures
remain evidence, without a compatibility reader. It retains raw browser epoch
anchors for status start/response and DOM replacement, plus the native capture
timestamp and existing frame/status identities. Durations still use browser
`performance.now()`. Native `state.timestamp_ms` describes the retained capture
when `frame_ok`, not a renewed publication time. Offline subtraction requires the
same host/wall clock and scrutiny of clock adjustments; negative cross-clock
differences are retained rather than silently clamped. Failed, superseded, stale
or disconnected frames do not establish current presentation. The paused no-game
browser probe verifies v2 status anchors only; actual paired native/browser
correlation remains to be measured during fresh play. Animation callbacks do not
establish screen paint, and these records do not isolate model inference.

The timing disclosure offers standard Download timing and **Show export JSON**
over the same complete bounded page history, including overflow and failures.
The latter writes one fixed, visible DOM snapshot for human or browser-automation
collection. Live polling does not rewrite that export; click again to refresh it.
This avoids requiring a browser download-event API. It adds no endpoint, store,
sampling protocol or gameplay action, and neither export surface qualifies speed.
Collect after the measured interval and before reload/closure; retain actual
status/frame counts and missingness rather than treating a status-only probe as
native/gameplay display evidence.

Campaign length is another profiling axis. Current ingestion scans retained peers,
capacity accounting walks frame files and archive save serializes the manifest.
Navigation rechecks accumulated source files/hashes. Profile those stages against
archive and route-source counts before replacing storage or introducing a cache.
Required loss/correction/integrity and current-authority checks must remain;
reuse the existing SQLite/journal if evidence establishes a storage gap. #154
owns this follow-up without adding a new framework gate to the current mission.

## Caller contract

Use `RunRecorder(manifest)`, `record(event)`, `finish(outcome)` and `write(path)`
from [evaluation.py](../harness/gameplay/evaluation.py). Its `run_schema()` returns
the exact JSON Schema; module documentation describes payloads. Validation adds
sequence, missingness, provenance and identity checks beyond the schema. There is
one current artifact format, `evaluation/1`; unsupported formats reject.

Capture admission monotonic time before planning or dispatch. Event `elapsed_ms`
is completion time minus admission, with a duration ending at that time. Finish
with the actual final elapsed time, including post-event waits/timeouts. Native
game turns are signed identities; turn consumption requires same-session endpoints.
Retain real `EvidenceRef` objects from the evidence store for native start/final
observations. Structural validation cannot verify frame bytes or prove a judgment.

Record one action event per primitive attempt, including rejected and uncertain
attempts; use a unique action ID and explicit dispatch state. Expand bounded walks
from their observed primitive records. Preserve partial verified progress even
when a run fails. First useful action requires known dispatch and an independently
explained judgment; delivery alone is insufficient, and useful nonmovement inputs
may have zero displacement. Missing measurements need a reason, never a fabricated
zero. Record failed model calls and their actual usage/cost; cached input is a
subset of input tokens. No private reasoning transcript belongs in these records.

Configuration identity identifies the whole declared condition, including possible
models and routing policy. Change it when that configuration changes. Summaries
group by declared family/split/lane/condition/source/native/model/configuration/
protocol identity. Session and realized call subsets are provenance: reloads and
pre-call failures stay in their cohort. Actual role/model/configuration usage is
also reported within the cohort. Do not infer that a shared label proves identical
configuration; retain the configuration and assessment evidence with each run.

`finish` seals the recorder; writes create a new file exclusively. Failed validation
does not discard prior accepted records. Bounds are 4096 events, 8 MiB per run,
4096 characters per string and 64 evidence references per list. These are evidence
bounds, not enforcement of the declared gameplay budget: the supervisor must stop
execution, and the recorder must retain any observed overrun.

## Offline review

The [waypoint execution-readiness decision](changes/014-waypoint-readiness.md#execution-readiness-decision)
distinguishes the implemented bounded skill path from missing matched-arm execution,
runtime recorder export and trial/model measurement preparation. Condition names
in this schema do not establish executable experimental arms.

From the project root, using project-local files:

```sh
.venv/bin/python -m tools.evaluate validate .runtime/evidence/run.json
.venv/bin/python -m tools.evaluate summary .runtime/evidence/run.json
```

Both commands accept multiple paths, reject any malformed/duplicate run rather
than skip it, and print JSON without changing evidence. CLI input is bounded to
64 MiB and 4096 files. Summaries retain unknown and budget-censored runs; report
known subtotals and missing counts, outcome coverage, progress, interventions,
harms, elapsed time, calls and median/nearest-rank p95 durations. Read coverage and
sample size before comparing totals. Synthetic fixtures test accounting only.

Maintain the schema, callers, tests and this guide together. On a format change,
preserve historical evidence and migrate active consumers as one coordinated
change; no fallback reader. Revisit missing instrumentation and independent outcome
labeling before #24/#44 trials and after any false-success or accounting incident.

The spectator timing view keeps the latest 32 samples on screen. Its standard JSON
download includes up to 8,192 samples per stage retained in that open page and explicit
overflow counts; earlier sessions on the same page are included. Save the download
in the run evidence directory before closing/reloading the tab, then filter by the
frozen mission's actual native sessions and time interval. A successful download
proves export, not complete coverage: inspect overflow, page lifetime, clock
continuity and exact useful-effect matching before a latency claim. No telemetry
is submitted to the controller and no physical-paint measurement is added.

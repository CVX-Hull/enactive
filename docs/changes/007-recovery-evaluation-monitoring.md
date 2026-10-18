---
owner: lead
review_trigger: Recovery ingress, evaluation records, monitor design or round ownership changes
status: active
---

# Public recovery, evaluation foundations and monitoring design

Round: #31, #18 and #41. Source base:
`b6cfcbfed175f11ab95828d70239b14f1656cdd9`. This is an implementation brief;
current architecture/protocol remain authoritative about shipped capabilities.
The lead owns integration and @CVX-Hull is accountable. GitHub owns live status.

## User outcome and boundaries

Expose the accepted operator recovery operations in the ordinary-window spectator
and CLI. Establish an honest measurement protocol before autonomous waypoint
experiments. Separately design how future tasks can use reusable expectations and
fallible monitors without weakening deterministic authority. #41 does not gate or
expand the existing waypoint task. #8 retains broad native recovery acceptance;
#24 retains live model comparisons; #42–#44 retain general monitor implementation.

No provider or spending is selected, no training is started, and no new global
tooling is installed. All game observations remain player-visible. Preserve saves,
unknown actions and the existing pause limitation on already-committed inputs.

## Recovery ingress contract — #31

Add `POST /api/recovery`, separate from `/api/command`. Reuse the existing exact
loopback Host/origin, token, content type and 4096-byte request constraints.
Reject unknown fields and invalid types; never fill authority fields from a later
observation. Only the three existing `Controller.recover` operations are accepted.
The ordinary command endpoint continues to reject recovery operations.

| Kind | Caller-supplied payload, besides kind and optional timeout |
| --- | --- |
| `request_interrupt` | `expected_session`, `expected_control_generation` |
| `answer_interrupt` | Those fields plus `expected_boundary_id`, `expected_revision`, `expected_frame`, `interrupt_request_id`, `choice` (`YES` or `NO`) |
| `continue_debug_once` | Session/generation plus `expected_boundary_id`, `expected_revision`, `expected_frame` |

HTTP 200 means a reported `prompt_opened`, `answer_delivered`,
`dismissal_delivered` or `not_applicable` result, not successful cancellation.
Rejected/unknown/controller errors use 409; invalid input uses 400; existing
authentication and size errors retain their codes. Preserve the complete response
and error evidence for both HTTP success and failure.

CLI subcommands use the exact operation names above. Require `--session` and
`--generation`; answers/debug also require `--boundary`, `--revision`, `--frame`;
answers require `--interrupt-request-id` and `--choice YES|NO`. Optional timeout
uses the existing finite positive upper bound. The CLI never fetches new authority
to fill a missing flag or opens a second native writer. It uses the discovered
current service and the separate endpoint. Usage/help explains delivery uncertainty.

The spectator shows Request interrupt, Yes, No and Continue debug once only as
eligible operations, distinct from Pause and Resume. Eligibility requires current
successful decoded frame, fresh matching session/revision/frame and boundary
identity/generation plus the advertised operation; answer requires matching
interrupt ownership. Request interrupt need not carry a world-turn revision in
its payload. It still needs a fresh displayed activity boundary. Native gates
remain final authority. No arbitrary keys or generic YESNO permission.

Maintain separate gameplay and recovery in-flight state: a long ordinary request
must not prevent interrupt, and Pause must remain available during either request.
Disable duplicate recovery while its request or unresolved control slot exists;
Observe stays available for explicit reconciliation after expiry. Late requests
cannot enable stale controls. Show original gameplay pending/unknown separately
from recovery pending/unknown, including after reload. No automatic answer,
resume, retry or implication that delivery proves cancellation. Narrow-layout
readability and keyboard labels are part of acceptance.

## Evaluation data contract — #18

Use an independent passive module `harness/gameplay/evaluation.py`, with existing
JSON Schema validation rather than a new validation framework. Add
`tools/evaluate.py` for offline trace validation/summary only. Neither imports or
dispatches through controller/server/native code. Future planner/supervisor ports
will emit these records; this increment supplies an explicit recorder API and
documents how legitimate native measurements were recorded. It does not claim
that unimplemented model calls are instrumented automatically.

One current format, `evaluation/1`, is a complete bounded JSON run artifact:

- Manifest: run/scenario/family IDs; development or held-out split; synthetic or
  native lane; condition (primitive, bounded_skill or same_model_roles); source
  commit; native build and model/configuration identity (nullable with a reason
  when inapplicable); protocol version; declared primitive/turn/wall/model-call
  and financial budgets; legitimate start description and evidence references;
  initial game turn (nullable with a missingness reason). Elapsed time starts at
  run admission, before planning or action, using a monotonic clock.
- Ordered events: unique event ID, nondecreasing elapsed monotonic milliseconds,
  event kind, optional game turn and immutable evidence references. Timestamp is
  the event's observed completion time relative to admission; duration, when
  present, ends at that timestamp and cannot exceed it. Supported
  event kinds are action, observation, model_call, intervention, recovery and
  decision. Each has an exact payload schema; reject arbitrary extra fields.
- Action payload: one record per primitive attempt with unique action ID,
  transport disposition, dispatch state (`not_dispatched`, `dispatched` or
  `unknown`), duration, observed verified steps or null, invalid/stale/unknown
  flags and verified no-progress. A bounded walk is expanded from its primitive
  evidence, never counted as all requested steps. Count attempts, known dispatches
  and unknown dispatches separately; do not add duplicate action IDs. Observe and
  model calls are not primitives. Preserve progress independently of disposition.
- Model-call payload: role (planner, tactical, monitor, verifier or router),
  model/configuration, duration, input/output/cached-input tokens and cost in USD.
  Usage/cost may be null with a reason; cached input is a subset, never added to
  total input. Record failed and timed-out calls and their observed cost too.
- Observation payload: duration and freshness/availability. Intervention and
  recovery payloads distinguish operator intervention from autonomous repair and
  retain outcomes. Decision payload records continue/inspect/escalate/replan/stop,
  public reason, actor/model, expected/observed claims and unknowns with factual
  versus interpreted evidence; no private reasoning transcript.
- Final outcome: success, partial, failed, unknown or budget_exhausted; verified
  progress; first useful action event ID or null with reason; harmful actions and
  death counts nullable with missingness reason; current evidence and independent
  assessment method. Require final elapsed milliseconds even if the last event
  predates a wait/timeout, plus final game turn and missingness reason if unknown.
  Final elapsed time is at least the last event time; game-turn totals require
  valid same-session endpoints and never bridge a world reload. Unknown/missing
  labels cannot become zero or success.

Expose `RunRecorder(manifest)`, `record(event)`, `finish(outcome)`, `to_dict()`
and `write(path)`, plus `validate_run(value)` and `summarize_runs(runs)`.
The worker may choose precise typed signatures while preserving these semantics.
Use standard JSON, pathlib and statistics plus the existing jsonschema package.
No database, telemetry service or dependency installation. Bound to 4096 events,
8 MiB serialized run, strings at most 4096 characters, evidence lists at most 64
references per record, and finite nonnegative numeric measurements (native game
turn identities retain their signed 32-bit contract). Reject booleans
as numeric measurements. Write exclusive artifacts; no overwriting evidence.
Schema/validation failures must not silently omit an event or whole run.

Summaries retain every failed/censored run and split results by lane, scenario
family, development/held-out split, condition, source/native build and complete
model/configuration identity. Never pool different identities into a comparative
total. Configuration identity describes the complete predeclared routing policy,
including possible models. Session identity and the realized subset of model calls
are provenance, not grouping keys: a reload or pre-call failure must not split a
repeat out of its cohort. Report actual per-call identities within each cohort.
Derive wall time and game-turn totals from explicit run endpoints, not the
last event. Report outcome counts/coverage, partial progress, harms,
deaths, intervention/recovery and invalid/stale/unknown/no-progress counts,
primitive and game-turn totals, wall time, time to first useful action, model
switches, role-specific call/usage/cost totals and duration distribution including
median and nearest-rank p95. Mark incomplete totals with their known subtotal and
missing count; never turn unavailable API costs into free calls. No efficacy claim
from mixed scenarios or synthetic fixtures. Offline replay cannot establish an
unexecuted action's outcome. Hand-labeled judgments disclose assessor and method.

## Waypoint experiment protocol

Initial comparison for #24: same capable model chooses individual primitives
versus the same model chooses bounded skills. Same-model role separation is a
separate third condition only after budgets and interfaces are fixed. No model is
selected by this brief. Use the design's 1–4 tile outward-and-return task.

Development families: unobstructed route; visible blocked next tile; prompt or
missing/stale observation; operator pause. Held-out families: a different visible
route/starting position, new visible-creature interruption, same-process world
reload/goal replacement and partial-progress interruption. Use legitimate saves,
ordinary movement and native UI, never save edits or hidden map inspection.
Synthetic variants test control plumbing; native cases prove only encountered
conditions. Unsafe or unavailable starts remain recorded as unavailable, not a
passing substituted fixture. Scenario selection cannot inspect held-out outcomes
to tune the policy. Repeated starts need their own visible-state evidence; do not
assume deterministic replay or identical game RNG.

Before the deciding experiment, freeze a feasibility-reviewed scenario catalog:
at least four feasible native families, five repetitions per condition/family,
with development and held-out families disjoint. Paired comparisons disclose
imperfect start matching. If a family cannot be induced legitimately, revise the
protocol with rationale before any deciding trial, not after seeing results.
Each run retains the current limits of eight primitives, 32 game turns,
120 seconds and ten model calls, with each call at most 30 seconds. Provider/model,
token and explicit USD ceilings remain required before live calls; absent ceilings
disable live model execution. No retrospective budget increase for failed runs.

Predeclared decision: require no authority violations or hidden-state dependence;
no observed increase in harmful outcomes; and no decrease greater than one success
per matched family (five repeats) before treating a cost/latency gain as promising.
Require at least 20% lower median total model/monitor/router/recovery cost or wall
time, and report p95 tradeoffs and all censored outcomes. These are practical pilot
thresholds, not statistical equivalence or a safety guarantee. Small or inconsistent
samples produce defer/further-evidence, not a confident adoption. Report counts and
uncertainty; do not optimize solely on successful runs. #18 validates the recording
and protocol, with known synthetic traces and at least one real native trace; #24
executes the frozen model comparison later.

## Monitoring design — #41

Lead publishes a separate proposed monitor contract, referenced by the scoped
gameplay design without replacing its waypoint predicates. Include three-valued
claims, observation availability, read-only monitor interface, declarative
expectation composition, progress/failure/completion separation and bounded
escalation/replanning, including strongest-model fallback. Provide three worked
families, an accessible rendered diagram and a primary-source evidence matrix with
dates, read depth and transfer limitations. Explicitly compare reusable facts,
direct model monitoring and learned predicates; training remains conditional.
Specify ownership, maintenance/calibration/retirement triggers and reviewed
migration of consumers when future implementation replaces any record.

## Delegation, review and acceptance

| Owner | Exclusive source paths | Checks and return evidence |
| --- | --- | --- |
| Recovery worker | `harness/server.py`, `harness/__main__.py`, `web/app.js`, `web/index.html`, `web/style.css`, `tests/test_server.py`, `tests/test_cli.py`, `tests/test_viewer.cjs` | Focused HTTP/CLI/viewer regressions, common checks where possible; diff/commit, failures, limitations |
| Evaluation worker | `harness/gameplay/evaluation.py`, `tools/evaluate.py`, `tests/test_evaluation.py` | Meaningful exact-schema, accounting, incomplete/censored, ordering/limits and CLI tests; no native claims |
| Lead | This brief, all current/research/design/acceptance docs, diagrams, shared controller/contracts if justified | Interface adjudication, source inspection, native/public-surface probes and measurement, common checks, publication |
| Independent reviewers | Read-only relevant candidate and contracts | Clean-context security/control, accounting and design evidence; lead resolves findings |

Workers use separate project-local worktrees from the reviewed brief commit; lead
records exact SHA and paths in each dispatch. At most two writers, no shared runtime
or environment mutation. Escalate after two failed repairs or scope drift. Source
integration, native builds, game/saves, ports and diagram rendering are serialized.
Use the existing project Python read-only with bytecode disabled; do not install
packages or write the lead's caches. Workers run focused checks without shared-cache
writes; the lead runs the complete common suite on the integrated candidate.

Lead probes public recovery on real WAIT YES/NO and raw debug, remains paused,
inspects stale/missing-frame controls and captures actual spectator/CLI evidence.
Preserve unexpected game behavior. Reuse the accepted native build only if native
sources/pins are unchanged and receipts match; otherwise rebuild and revalidate.
Native #8's broader coverage remains open. #18 needs at least one recorded native
measurement, but neither that sample nor fixture results prove model competence.

Original effort estimates remain #31 M/Medium 1–2 focused sessions plus native
integration, #18 M/Medium 2–4 sessions and #41 M/Medium 2–3 sessions. These are
provisional effort, not elapsed dates or approved resource spend. Interface or
validation expansion triggers explicit re-estimation. Publish coherent PR(s),
verify exact-candidate CI, merge through branch protection and read back acceptance
and tracker fields. Retire this brief as dated history after verified delivery.

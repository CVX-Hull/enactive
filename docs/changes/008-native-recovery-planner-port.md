---
owner: lead
status: active
review_trigger: Native pause semantics, planner interface, ownership or acceptance changes
---

# Native recovery acceptance and bounded planner port

Round 008 selects #8 and #34 from clean main
`2e7baf903f89ab0eef886eac6116887f8263c10a`. The lead owns design,
integration and verification; @CVX-Hull is accountable. GitHub owns live stages.
This brief defines implementation work, not an assertion of shipped behavior.

## Outcome and sequencing

Make an eligible interruption usable without first performing a separate
Pause/Observe workaround, and verify the integrated native recovery contract.
Independently supply a bounded, injected planner port for later supervision.
Neither outcome starts an autonomous task or enables a live model provider.

Execution correction: a suspected blank raw-debug frame was independently
verified readable in its retained pixels; the visual interpretation was wrong.
Temporary diagnostic builds remain separate evidence; they were removed before
resuming production acceptance on a rebuilt, separately identified candidate. No renderer repair is justified by that finding.

Native revocation timing uses a separately identified acceptance-only build with
bounded one-second barriers immediately before claim, immediately before the
existing final commit checks, and after commitment. These barriers change timing
only; public Pause supplies revocation, and all native checks and actual input
delivery remain intact. Retain its source diff, binary hashes and marker trace.
This instrumented lane does not establish production timing. Restore the exact
retained production binary/source and verify normal gameplay afterward.

#7's implementation children #29–#31 are accepted; its aggregate is closed.
#18 and #32 supply accepted evaluation and typed records. #33 remains blocked
until #8 passes. #20 stays next; #35/#36 and semantic monitoring are outside this
round. Avoid a second runtime owner merely because source work can parallelize.

## Native change and limits

The retained round-007 probes show immediate unpaused interruption rejecting
because `poll()` increments revision on seeing the host pause sentinel before
`poll_control()` checks the saved activity frame. `Controller.recover()` first
revokes durable host authority and writes this sentinel. The game-thread pause
transition itself changes no game input, boundary, turn or rendered scene.

Preserve native scene revision on this transport-only transition. Still latch
`paused`, mark status dirty, and process pause before recovery and ordinary input.
Do not relabel an old frame, assign a new capture timestamp, refresh/retry input,
or move recovery ahead of Pause. Keep all frame/session/boundary/freshness checks
and the final recovery authority gate. Coordinate the evidence consumer: remove
`paused` from `EvidenceStore._scene_authority` comparison across distinct frames
at one revision, because it is transport control state rather than a game fact.
Keep `paused` in immutable per-frame metadata and retained observations; rewriting
metadata for the same frame must still dispute it. Preserve all actual scene,
boundary/action and revision conflicts, current-frame invalidation and host-token
gates. A regression must ingest unpaused then paused normal-play frames at the
same revision without disputing historical scene facts, while changed terrain
at that revision still invalidates the cohort. Native probes must verify this
actual capture sequence. Native keyboard takeover, world/boundary/
turn changes, resume and actual injected inputs still invalidate their current
identities. Repeated host Pause still revokes its durable token even when already
paused. A later Pause cannot undo an input committed at the final gate.

The alternative of automatically capturing again before recovery would change
the evidence underpinning the operator's decision. Reordering recovery before
Pause risks weakening revocation. A new wire format is unnecessary if the above
invariant is confirmed: scene identity and host authority already have separate
fields. If inspection or real probes contradict it, stop and revise this design;
never relax guards to obtain a demonstration.

The lead owns `native/cdda_harness.cpp`, any justified native header/patch changes,
`harness/controller.py`, `harness/gameplay/evidence.py`,
`tests/test_gameplay_evidence.py`, relevant existing tests, native probe drivers and current
docs. Preserve a reproducible public-surface regression driver and before/after
receipts for the immediate-interrupt case. Existing portable revocation tests must
remain green; a source-text assertion is not behavioral proof of this repair.

## Planner interface and trust boundary

Worker paths: `harness/gameplay/planner.py` and
`tests/test_gameplay_planner.py`. No other writes without an amended brief.
Use standard-library immutable dataclasses, threading/events/locks/monotonic time,
and existing gameplay records/JSON Schema. No new dependency or SDK is needed.
This port validates data and manages call lifecycle; it never dispatches inputs,
owns a controller lease, opens files, performs network calls itself or launches
processes. The injected provider is trusted integration code, not a sandbox for
arbitrary Python. A future network adapter must be separately implemented outside
the passive record boundary; this round does not relax Import Linter wholesale.

Expose a small documented API: immutable configuration, immutable planning request,
provider reply/usage, `PlannerPort.submit`, `poll`, `cancel`, `close`, and bounded
accounting snapshots. Exact Python names for record types may follow module style.
One port belongs to one task run; lifetime budgets cannot reset through continuation.
It supports no journal restoration or implicit restart of calls. Construction
requires an immutable caller-supplied `admission_monotonic` from task admission,
the same origin as the evaluation manifest (seconds versus milliseconds converted
explicitly). It must be finite, nonnegative and not in the future. Creation or a
delayed first submit cannot reset that origin; reject a different task identity or
admission origin. Original TaskSpec lifetime ceilings and each packet's declared
remaining ceilings both constrain admission; neither replenishes prior usage.
Test delayed first submission and continuation without clock/budget reset.
Pin the exact initial `EvidencePacket.start` on the first invoked call; reject
replacement on continuation, so changing the start cannot replenish turn budget.

Request carries TaskSpec, EvidencePacket, a nonempty tuple of accepted supplied
SkillDescriptors, plan/version/execution epoch, the expected next stage and exact
remaining distance, plus bounded supplied public context. The caller, later the
supervisor, establishes current route progress; the model cannot choose a different
stage or inflate remaining work. Verify task/packet/plan/session relationships,
normal-play evidence, and all numeric/type/bounds before invoking the provider.
Capability descriptors are supplied by the caller; the port does not claim that a
fixture descriptor proves an implemented skill. Do not infer authority from memory.

The provider receives only an immutable input snapshot and cooperative cancellation
event, with explicit context/output limits. It returns bounded serialized
PlanCandidate JSON plus observed usage, never executable code. Reject wrong schema,
extra fields, oversized/nonfinite/invalid data, unsupported skill/version, stale
task/plan/epoch/session/revision, stage/direction/remaining-distance mismatch. Reuse
`PlanCandidate.check_binding` and add the request-specific exact checks it does not
provide. Accepting a candidate grants no live execution authority; the later
controller must separately validate its run lease and fresh native evidence.

`submit` returns a unique call identity. `poll` accepts the caller's current binding
for applicability checking; a stale result becomes terminal and cannot later revive.
Cancellation/deadline/close win over a provider that subsequently returns. A lock
serializes state transitions and reservations, not the provider call. One bounded
daemon thread may run a provider outside that lock; do not use an executor whose
shutdown waits indefinitely. Cancellation signals the provider but cannot forcibly
kill trusted Python/network execution. Keep that physical slot occupied until the
provider exits, including after timeout; reject new calls rather than leaking
threads. Retain at most ten calls and 64 uninvoked audit records (overflow must
be explicit, never silent eviction). Context and reply each have a hard 1 MiB
ceiling; input/output token ceilings are each at most 1,048,576. Public context
is at most 4096 characters, and at most 32 descriptors may be supplied. Defaults
are 1 MiB context, 16 KiB reply, 32768 input and 2048 output tokens; actual future
providers must additionally respect their own limits. Bound public errors.
Close forbids new work, invalidates applicability and returns without waiting for
a stuck provider. No call, completion or cancellation automatically retries.

## Budgets and accounting

Configuration names explicit model/configuration identities, mode `fixture` or
`network`, maximum context bytes/input tokens/output tokens, call count/deadline,
and finite nonnegative maximum USD reservation per call and per run. Limits cannot
exceed TaskSpec's remaining call/time/spend bounds. Use one admission monotonic
origin; task lifetime and call deadlines are distinct and are checked on submit,
poll and completion. Enforce one physical provider call and at most ten lifetime
calls. Do not claim a byte count is a universally accurate model tokenizer.
The adapter contract must honor the provided input/output ceilings; use the
configured worst permitted call cost for reservation, not a guessed token count.

Network mode additionally requires explicit credential availability, known bounded
pricing/reservation and a positive operator-approved spend ceiling. Missing values
disable invocation. Fixture mode is explicit and cannot be used to claim real
provider performance or free external planning. No live calls occur in this round.
Reserve before invoking; never oversubscribe through concurrent submit. Missing
cost, malformed or contradictory usage retains the conservative reservation.
Valid independent actual cost can settle when token counts are merely unavailable;
retain explicit reasons for those missing token metrics. Valid actual cost within
reservation settles once. Report an adapter exceeding its declared
bound as a fault and actual overshoot; freeze future calls rather than hiding cost
or claiming the port can prevent a misbehaving provider from overspending.

Retain separate applicability, invocation/stop/settlement timestamps, observed
usage, unresolved reservation and public reason. Timeout/cancellation does not
erase failed/late cost. Late settlement may update accounting only, never expose
a candidate. A snapshot exposes exactly one evaluation/1 model-call event per
invoked call at its reporting cutoff; uninvoked rejections are separate audit
records, not model calls. Cancellation maps to `unknown` with a public lifecycle
reason; existing evaluation statuses need no alias or compatibility path.
Unsettled usage/cost is null with a reason, never zero. Record physical provider completion separately from financial settlement. Duration
ends at provider completion even when usage/cost is missing or invalid; only a
physically unfinished invocation is censored at the reporting cutoff. Test a
completed one-second call with unknown cost at a much later cutoff.
Keep the earlier stop timestamp separately so this is not mistaken for stop latency.
Snapshots are assembled into a recorder once at an explicit cutoff, not appended
repeatedly as duplicate calls. Later knowledge requires a new distinctly named
artifact, retaining the earlier artifact; never overwrite evidence or double-count
a call. Test generated events with the real evaluation validator/recorder.

## Verification, delegation and publication

Lead first obtains clean-context review of this brief. Then checkpoint it and
dispatch one clean-context worker from that exact SHA to a project-local worktree.
Worker uses the existing Python environment read-only, bytecode/cache writes
disabled, and returns its diff, focused checks and remaining risks. Lead works on
the disjoint native paths. Escalate after two failed repairs or ownership drift.
Independent reviewers check code, changed tests, accounting and acceptance claims.

Planner acceptance includes deterministic controllable providers: valid output,
bad schema/bounds/identity/semantics, missing credentials/prices/budget, concurrency,
deadline, cancel/close racing completion, stuck provider resource ceiling, late
settlement, missing/over-reservation usage and cumulative budgets. Fake-clock tests
must not disguise a blocking production wait. Verify bounded real waits as needed.

Native acceptance follows every row and named risk in
[native-control](../design/native-control.md#supported-scope-limits-and-acceptance). Record which
probes are live game, host transport fault injection or portable fixtures. Use
fresh pinned extraction/build provenance, ordinary windows and actual public
controls. Preserve the old installed binary/build receipt for rollback until the
new candidate passes. Probe YES/NO, immediate interrupt, finishes-before-claim,
stale/revoked authority, original/control result loss, restart/reload, capture loss,
raw/nested debug and unsupported paths; measure scoped latency/backlog behavior.
Never equate input delivery with cancellation or a mock with engine evidence.

Diagnose saved tutorial load failures from pinned source/data and visible loading.
Do not edit saves or ignore engine validation. A separate content defect may be
tracked with a concrete owner, evidence and next action; required recovery failures
cannot be deferred to close #8. Lead owns save/quit and all process cleanup.

No current serialized contract is replaced by the proposed initial implementation;
the planner API is new and native wire v3 stays singular. If that changes during
review, migrate every producer, consumer, test and retained current-format state
together before deployment. Preserve unresolved admissions and historical evidence;
never replay them. Roll back a coherent tested source/binary set, not mixed formats.

Current provisional estimates: #8 M/Low, 3–5 focused sessions; #34 M/Medium,
2–3 sessions, including review/rework. These are effort ranges, not elapsed dates
or approved resource budgets. Split/re-estimate scope expansion before Ready.
Run common checks, inspect staged diff, keep docs/current control evidence truthful,
then publish through exact-head hosted CI and protected merge. Close only accepted
outcomes. Revisit #5 only if all its scope is met; refresh #33's gate without starting
it. Finish clean main, remove only owned worktrees/branches/processes, retain saves
and evidence, and record any failed or unexecuted acceptance honestly.

---
owner: lead
status: active
review_trigger: Round 009 interfaces, ownership, acceptance or scope changes
---

# Bounded movement skills and native evidence

## Outcome and scope

Deliver #20 and #33 from clean main `a61733ae289a4ceca235bdfa6c78d0f38aeaa5b0`.
A caller can request one reviewed movement primitive and receive verified progress
or an honest stop. Native observations pass through the actual evidence store,
with original frames retained. This enables later supervision; it does not start
an autonomous player or connect a model. #19 closes only when #32 and #33 satisfy
its observation acceptance. GitHub owns execution status and estimates.

The existing public walk remains a bounded controller operation with its current
result shape, including `stopped` after full displacement. The new skill never
calls that loop or writes inputs. No supervisor/lease/run lifecycle, UI, semantic
monitor, live provider/spend, tutorial repair #47 or broad maintenance #13.

## Design and interfaces to freeze before dispatch

Reuse the actual guard rather than copy it or introduce a generic behavior-tree
framework. There is one cardinal policy in a new standard-library-only
`harness/movement.py`. The controller and gameplay skill both import it. The
existing directions/action names and terrain allowlist move there. The helper
has no controller, gameplay, filesystem or time-reading dependency.

- `guard(state, dx, dy, *, paused, frozen, now_timestamp_ms) -> tuple[int,int,int]`
  raises `MovementBlocked(ValueError)` with the existing walk reasons. It preserves
  the public guard's semantics. Malformed required values fail closed.
- `expected_position(position, dx, dy)` and `observed_step(before, after, dx, dy)`
  centralize exact displacement/session/category checks used by the public walk.
  Skills additionally require retained current normal-play evidence.
- The controller wraps `MovementBlocked` as `ControlError`, retains serialization,
  per-step observation, revocation, native dispatch and final guard behavior.
  No alternate input path or fallback implementation remains.
- Add `EvidenceStore.observation(reference) -> dict`: integrity/source-status
  checked, deep-copied historical observation. Disputed sources reject. It grants
  no freshness or authority; skills separately call `current` with caller clocks.
  It exposes only the already validated player-visible allowlist, not new exports.

The worker owns a task-bound `MovementStage` in `harness/gameplay/skills.py`.
It is bounded local proposal/result bookkeeping, not a dispatcher or run state
machine. Its explicit construction inputs are immutable TaskSpec, stage ID/version,
`outbound` or `return`, EvidenceStore, original task-start EvidenceRef, stage-start
EvidenceRef, original admission monotonic time and prior task primitive count.
Return also requires retained waypoint evidence at the target. The first version
starts a full leg at origin/waypoint; it does not implement continuation or replay
of interrupted legs. A terminal instance cannot be rearmed. Future continuation
requires its own reviewed remaining-route API rather than resetting this instance.

Constructor validates typed inputs and retained undisputed sources, same task
session, task origin/target positions, ordered turns and nonnegative original
clock/count. Every propose/settle clock must be finite, no earlier than original
admission, and nondecreasing across calls; invalid/regressing clocks terminate
without replenishing budgets. Stage-start must be current on first proposal. The original task
clock/turn reference and prior primitive count cannot be replaced later. Supplied
history is trusted caller data that must originate from the future supervisor;
this module cannot police arbitrary local callers or authorize a run.

`propose(action_id, *, now_monotonic, now_timestamp_ms, paused, frozen)` returns
one frozen `StepProposal` or a terminal `SkillEvaluation` (with no primitive). A proposal contains logical
unique action ID, exact before EvidenceRef, cardinal action, expected position
and bounded wait ceiling. There can be only one outstanding proposal. It checks
current evidence identity and route continuity, pause/freeze, the common guard,
registered action, remaining primitive/turn/wall budget and retention preflight.
At construction pin the store authority generation. Before each proposal require
that generation and exact checkpoint reference, and scan every credited/start/
waypoint source for retained undisputed integrity. A → B → A cannot restore intent.
At settlement accept only the pinned generation (same reference, no progress) or
exactly one increment for the correlated new after-reference. Any extra generation
change means intervening invalidation/observation: stop without granting new progress.
After valid settlement update the pinned checkpoint/generation. Recheck credited
sources before completion; a disputed older frame invalidates the claimed result.

The caller reserves after-frame capacity immediately before dispatch, rechecks
control authority and serializes exactly one native input. Proposal validity is
not a lease or dispatch permission. Consuming primitive budget happens at proposal
creation, conservatively even if transport later rejects it.

`settle(result: PrimitiveResult, *, now_monotonic, now_timestamp_ms, paused,
frozen)` matches the outstanding logical ID and exact before reference. It
independently computes displacement from retained sources; supplied displacement
must agree. Returned progress requires fresh current after evidence, exact expected
unit displacement, same session, nonregressing turn, advanced revision and no
source dispute. A different-world after frame can explain unknown context only.
Unknown/dispatched-only outcomes terminate unknown without credit or automatic
reconciliation; rejected/not-dispatched outcomes do not earn movement credit.
Rejected/not-dispatched outcomes and the first verified zero/unexpected displacement
are terminal, with no subsequent proposal from this instance. Repeated IDs cannot
increment progress; conflicting or unmatched results reject.
No later observation may silently turn an unknown action into success.

Settlement returns an immutable `SkillEvaluation` containing the PrimitiveResult,
verified Progress, reason and optional terminal StageResult. Missing/malformed
result data fails visibly without releasing an unresolved proposal for dispatch.
The common post-step guard runs even after the final displacement: full movement
can coexist with `blocked` or `interrupted`. A completed stage requires its target,
all requested verified steps, matching postconditions and no unresolved action.
Time/turn overshoot after a committed action is recorded; it cannot undo progress.
Stage evidence/counts are bounded by four primitives and the existing task limits.
Task completion, outbound-to-return selection, continuation, epoch/lease ownership,
non-progress re-admission policy and planner feedback remain supervisor duties.

Logical action IDs identify proposals and PrimitiveResult records. Native transport
IDs are independently generated by Controller. The trusted assembler must retain
an explicit one-to-one logical/native ID mapping, submitted action and before
session/revision with the native receipt; it must not guess this from a later
Observe. The manual native acceptance driver exercises and retains that mapping. Controller
`execute(action)` first observes and can return that Observe's ID, an ID-less
`pause_requested`, or an ID-less preflight error. The driver reads only its own
serialized controller journal segment for the call: mapping requires an actual
`kind=action` record with matching action/session/revision and native response ID.
An Observe UUID is never an action UUID. No action admission means not_dispatched;
an admitted action timeout/error means unknown unless an explicit native rejection
proves non-delivery. Missing or ambiguous attribution stops unknown, not success.
Preserve this mapping and classification in the driver evidence; do not change the
transport API or infer a movement receipt from the returned dictionary alone.
A ready response may be a menu/activity boundary or lack a valid frame; EvidenceStore
correctly rejects it. Preserve that raw native receipt/frame outside the task store,
settle unknown with after=None when displacement cannot be evidenced, and explicitly
release unused retention reservation. A successfully retained after-frame consumes
its reservation. Never substitute a later Observe as this primitive's after evidence.
The future supervisor owns automatic integration; no transport API change is
introduced merely to make the IDs equal.

A constant versioned cardinal-movement SkillDescriptor documents implemented
predicates, stop rules, actions and budgets. A registry is published only when
portable and required native acceptance pass; descriptors are declarations, never
an evaluator for arbitrary predicate strings. No runtime self-modification.

## Ownership and sequencing

Lead owns this brief, `harness/movement.py`, `harness/controller.py`,
`harness/gameplay/evidence.py`, their tests, shared contracts/import boundaries,
all current docs/control records and native evidence. Shared schemas stay unchanged
unless review proves a necessary coordinated change. Helper API is implemented and
checked before the worker starts; record that exact descendant of the reviewed
brief commit as worker base. One isolated worker owns only
`harness/gameplay/skills.py` and `tests/test_gameplay_skills.py` in
`.runtime/worktrees/bounded-skills`; no shared runtime or source edits.

Lead may inspect the existing native pipeline while the worker implements. Native
skill acceptance follows integration. Independent reviewers inspect the source
and evidence separately. Lead verifies their claims, integrates once and publishes.
S-AGENT's two-writer limit, disjoint ownership and escalation rules apply.

Provisional estimates include rework/review: #20 M/Medium, 2–4 focused sessions;
#33 S/Medium, 1–2. These are uncalibrated effort ranges, not delivery dates or API
budgets. Re-estimate if observation gaps or extraction materially expand scope.

## Acceptance and maintenance

Portable checks cover guard parity, required malformed fields, all cardinal paths,
registered bindings, pause/freeze, stale/missing/disputed evidence, unsupported
boundaries, creatures/blocked terrain, wrong displacement/session, budget edges,
duplicate/mismatched results, no progress, full movement followed by stop and
unknown outcomes. Use real EvidenceStore fixtures, not a permissive fake store.
Re-run public walk regressions and the common command. Record failures and fixes.

Native acceptance maps each predicate to its source and retained frame, and
explicitly lists exclusions (damage, traps, unseen terrain/creatures, inventory).
Use the current restored binary only after source/hash verification. Exercise
normal/menu/activity boundaries, stale/missing capture, save/reload/session changes,
actual position/turn continuity and visibility restrictions through EvidenceStore.
Adversarial injected metadata is labeled portable/fault evidence, never native
proof. Run a real short outbound and return using one proposal/action/settlement
at a time; retain logical/native mapping, per-step frames/results and terminal
outcomes. Show the actual graphical spectator, inspect failures, save/quit normally.
No hidden-state reads, save edits or engine-validation bypasses.

Preserve prior evidence and saves. This adds internal APIs, not a persisted-format
or wire-version replacement. Moving the existing policy removes its old copy and
migrates both consumers together; no compatibility shim. Native changes, if needed,
require a reviewed migration/build and relevant native probes. Rollback is a
coherent earlier source/binary set, with retained evidence remaining historical.

Update current architecture/protocol/overview/runbook and stale gameplay design
module status; link the new evidence from work.md. Update control exercise/review
records with bounded claims. Render and inspect diagrams only if their described
flow changes. Publish through exact-head protected CI and verify merged-main CI;
close only accepted issues, refresh downstream gates without starting them. Retain
small manifests in Git and local media with hashes. Clean owned runtime/worktrees/
branches without deleting saves or diagnostic provenance.

## Brief review checkpoint

Independent review found five design gaps: intervening evidence invalidation,
Observe/action ID confusion, accidental reproposal after unsuccessful settlement,
unsupported-result retention, and regressing budget clocks. The interface above
addresses each. Independent rereview found no remaining design blocker. Baseline
common checks passed 231 Python tests plus viewer, dependency and documentation
controls; this is readiness evidence, not skill implementation or native acceptance.

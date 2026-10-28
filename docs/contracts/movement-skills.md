---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Passive bounded movement skills

`harness/gameplay/skills.py` implements `MovementStage` and the versioned
`CARDINAL_MOVEMENT` descriptor. `ACCEPTED_SKILLS` contains this one capability.
Descriptors declare implemented predicates; arbitrary strings are not executable
conditions. Cardinal skill version4 supports the remaining part of outbound/return
legs of 1–4 steps using the TaskSpec's original primitive, turn and wall budgets.
The module never sends input, acquires authority, automatically resumes or retries.

Construction binds the immutable task, original task-start/admission, current
checkpoint and a tuple of settled `RouteAttempt(stage, result)` values. The
`summarize_route` function derives task/leg attempts, verified steps, waypoint and
position from retained originals. IDs must be unique, references ordered in the
same session and each before-position continuous with the verified route. Exact
returned steps advance; explicit non-delivery and returned zero consume attempts.
Unknown/dispatched-only or wrong displacement cannot become resumable history.
Only a complete outbound prefix permits return. Caller provenance must originate
from skill settlements or the reviewed revoked non-delivery exception; geometry
alone does not authenticate native receipts. Arbitrary Python callers gain no
execution authority from these types.

A new stage begins at the derived checkpoint and preserves cumulative leg progress,
leg/task proposal counts, original turn reference and admission clock. A terminal
instance never rearms. A complete leg can be freshly verified without creating an
action, even at exactly exhausted primitive budgets, but never after budget overshoot.
There is one constructor and descriptor version; full-leg/count-only callers are
removed. Historical round009 drivers are evidence, not supported current callers.

`propose` returns a frozen `StepProposal` or terminal `SkillEvaluation`. Exactly
one logical action can be outstanding; proposing consumes primitive budget even
if later rejected. Every call requires finite nondecreasing clocks. The checkpoint
and EvidenceStore authority generation must match, all credited/start/waypoint
sources must remain undisputed. The shared `current_guard` requires fresh normal
play, unpaused/unfrozen control, closed bounded visible-creature evidence with
every`hostile` value exactly false, and valid current
position. A registered cardinal action is required even at completion. At an exact,
fully credited target this current-boundary check suffices; before any further step,
the full `guard` additionally requires a CLEAR allowlisted furniture-free cardinal neighbor.
Evidence still requires all eight cells: an invisible future neighbor may omit its
hidden contents, but a missing cell is invalid. Public controller `walk` retains its
conservative next-neighbor check after every step. Prior cardinal descriptor versions
reject; no fallback descriptor or reader exists.

The caller reserves after-frame capacity, rechecks authority and serializes one
input. Logical proposal IDs differ from native UUIDs. The caller must retain an
exact mapping from its journaled action admission and outcome; the controller's
preflight Observe UUID is not an action receipt. No action admission means
`not_dispatched` only when the call's non-dispatch is established. Transport
uncertainty remains `unknown`. A later Observe cannot replace a missing result.

`settle` requires the exact logical ID and before-reference. It computes displacement
from retained observations independently. Verified movement requires the current,
fresh after-frame, same session, advanced revision, nonregressing turn, exact unit
displacement and no intervening generation change beyond that after-reference.
Duplicate results cannot add progress. Malformed or conflicting results cannot
release an unresolved proposal. Unknown/dispatched-only outcomes stop unknown;
rejection, non-dispatch and the first zero/unexpected displacement stop the stage.
Unsupported menu/activity or missing-frame results remain raw external evidence
and cannot be relabeled as normal-play evidence. Release unused reservations.

The final post-step guard runs even at the target: full displacement may coexist
with a blocked/interrupted result. Historical verified progress stays recorded
when older sources become disputed, but completion and new credit are forbidden;
the result becomes unknown. Completion requires the full target and all requested
steps. A committed time/turn overshoot is recorded as budget exhaustion without
undoing observed progress. `EvidenceStore.observation(ref)` supplies an integrity
checked deep copy of retained history; it never refreshes authority or freshness.

The [passive supervisor](#passive-waypoint-supervision) owns task completion, handoff, epochs and nonprogress
readmission. This is a passive study component; the retired waypoint runtime no longer
connects it to live input. MissionRuntime uses its own typed operation accounting. The [native acceptance](../acceptance/2026-10-17-bounded-skills.md)
proves a short manually driven example, not autonomy, trap safety or general survival.

## Passive waypoint supervision

`WaypointSupervisor` has one serialized caller, immutable TaskSpec/run ID, original
start/admission, one EvidenceStore, TaskMemory and PlannerPort. It never imports
the controller or starts a background player. Explicit `start` begins planning;
`poll` admits only a candidate matching exact task/plan/version/epoch/session,
current evidence and remaining route. Changed evidence/generation cancels
applicability instead of rebasing an old candidate. While planning, no intent is
available. The original port owns asynchronous cancellation, physical slot and
accounting throughout continuations.

`propose` offers at most one frozen DispatchIntent bound to run/task, plan, epoch,
stage, skill version and StepProposal. `grants_dispatch_authority` is false.
`settle` requires that complete intent and its exact logical ID/before reference.
Only skill-verified movement earns progress; duplicate results cannot earn credit
twice and conflicting results cannot release pending state. Runtime reserves
evidence, acquires/rechecks the real lease, maps native receipts and serializes
dispatch. Merely obtaining an intent proves none of these.

An unresolved intent expires at publication time plus its bounded wait ceiling.
Every mutating API checks expiry before its own operation; polling and settlement
revoke applicability when `now >= deadline`, retain
pending context and forbid late credit. Explicit non-delivery can release the
pending attempt; other late outcomes stay unknown. Previously credited progress
survives; raw late displacement is evidence, not new verified task progress.

Outbound completion retains a waypoint and starts fresh return planning. Completion
requires both legs, retained start/waypoint/final evidence, fresh current-boundary guard,
current epoch and no unresolved primitive. Starting return planning still checks
the actual return direction with the full next-neighbor guard. Original wall time includes planning
and pauses; task and leg attempt counts include rejected proposals. A stop after
full displacement or budget overshoot preserves progress without claiming success.

Pause, takeover and replacement revoke the epoch and planner applicability. A
published intent remains unresolved until its exact outcome is known. After
revocation, an explicit `not_dispatched`/`rejected` result can record a charged,
no-credit attempt only when retained same-session references show no movement;
this is trusted transport testimony, not an inference from coordinates. Other
late outcomes stay unknown and cannot earn credit or resume. Abandonment retires
the instance; new tasks must be explicit. Session replacement cannot reuse an
old origin. Goal replacement must call `abandon`, then construct a new explicit
task; `invalidate` alone represents a resumable authority interruption, not
replacement. Unknown actions are not automatically replayed or reconciled.

Explicit `continue_task` preserves the original history and budget ceilings and
creates a fresh epoch and remaining-route plan. Already complete legs instead
take a verification-only path without a zero-distance plan or extra action. The
first zero movement stops. Its relevant observable signature must change and all
fresh guards must pass before readmission; changing timestamps/revisions/frame
bytes or asserting success in model text is insufficient. Pausing cannot erase
the blocker. Explicit non-delivery also requires a relevant change, except when
explicit continuation resolves its known operator-revocation cause. This
conservative cardinal policy is not a general semantic monitor.

`status` supplies RunStatus at explicit clocks with `lease_owner=None`; freshness
is not a lease. Accepted completion remains terminal except for explicit
abandonment. Its exact final verification checkpoint stays in status evidence;
later source disputes produce an integrity diagnostic and `fresh=False` without
rewriting historical completion. Foreign-session turns cannot restore reported
task budgets. `pending_intent` keeps unresolved context inspectable. Accounting
and evaluation event snapshots compose with the existing RunRecorder; the caller
and independent assessor supply manifest/outcome and missing measurements remain
unknown. Synthetic tests are not native efficacy evidence. See the
[reviewed design](../changes/010-passive-supervisor.md) for ownership, migration and
acceptance. The runtime adds production integration without making this package
a dispatcher. Planning revalidation and non-authorizing status inspection support
slow external decisions while preserving fresh-input guards.

[Contract index](../protocol.md).

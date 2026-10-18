---
owner: lead
status: active
review_trigger: Round 010 interfaces, ownership, acceptance or scope changes
---

# Passive waypoint supervisor

## Outcome and boundary

Deliver [#35](https://github.com/CVX-Hull/cdda-player/issues/35) from main
`cc5691ccd6574d723e57b9c9ffe2224f95d20511`. Compose the accepted evidence,
memory, planner and skill components into a single explicit waypoint-and-return
task. After reaching the waypoint, require a new strategic return decision.
The operator gains a reviewable, testable supervisory contract; this slice does
not connect the browser, a provider or the game to it.

An eligible intent is data, never a dispatch lease. #36 retains the atomic
controller lease, ingress arbitration, authenticated lifecycle and native receipt
assembler. No controller/service/UI/native changes, spend, semantic monitor,
tutorial repair or global environment changes belong here. Fixtures establish
composition correctness, not native/model effectiveness.

## Single current route contract

Lead replaces the full-leg constructor with cardinal skill version 2 before
worker dispatch. `RouteAttempt(stage, result)` is frozen; `RouteHistory` is an
immutable tuple of at most eight attempts. Each result originates from a settled
skill proposal, including rejected and not-dispatched attempts. An unresolved
proposal cannot enter resumable history. The sole detached-settlement exception
is explicit non-delivery of a revoked intent, defined below. The supervisor owns provenance: these
types do not authenticate arbitrary local callers or native receipts.

`summarize_route(task, store, task_start, history)` rechecks retained originals,
unique logical IDs, same session, monotonic revisions/turns, route continuity and
exact reported displacement. It derives task/leg proposal counts, outbound and
return verified steps, checkpoint position and waypoint reference. Only exact
returned unit steps advance. Returned zero and explicit non-delivery consume a
proposal without progress; wrong displacement, missing returned evidence and
unknown/dispatched-only histories cannot resume. Return attempts require a fully
verified outbound prefix. No counts or progress supplied independently by callers.

`MovementStage(task, *, stage_id, stage_version, stage, store, task_start,
checkpoint, admission_monotonic, history)` accepts the remaining route at that
checkpoint. It derives existing leg progress/counts from history, uses the original
start/admission for turn/wall budgets, and counts new proposals conservatively.
Progress is cumulative for that leg; the target stays immutable. Current evidence
must match the derived position and follow history. Every credited source stays
retained and undisputed. Terminal instances never rearm. If a complete leg needs
fresh post-stop verification, `propose` checks the fresh guard and original
budgets then returns completed without creating an action or consuming a proposal.
Zero remaining primitive budget permits this verification, but overshot time/turn
budgets never permit completion. No legacy constructor or descriptor fallback.

All maintained skill callers are presently in `tests/test_gameplay_skills.py`.
Migrate them and current protocol/architecture guidance together. Historical
round009 evidence and ignored drivers remain immutable, unsupported evidence.
There is no persisted route format to convert. `gameplay/1` and `evaluation/1`
record shapes remain unchanged; cardinal descriptor identity changes to version 2.

## Supervisor API and ownership

One serialized caller owns `WaypointSupervisor` for its lifetime. Constructor
accepts immutable `task`, `run_id`, `store`, `task_start`, original
`admission_monotonic`, `PlannerConfig`, injected provider and clock (for the port).
It constructs exactly one TaskMemory and PlannerPort; continuation reuses both.
No restoration from journals, background supervisor thread or internal dispatch.

Public operations take explicit monotonic and timestamp clocks. They reject
malformed/regressing clocks without renewing authority: mutating operations revoke
applicability and fail closed, preserving pending context; read-only snapshots
reject bad clocks. `start` admits once;
`poll` checks pending planner work and current evidence; `propose(action_id)`
returns a frozen `DispatchIntent` or no intent; `settle(intent, result)` records
the correlated outcome; `pause(reason)`, `invalidate(reason)` (takeover/session
invalidation), `continue_task()` and `abandon(reason)` control applicability.
Read-only `status` returns current RunStatus; `pending_intent` remains inspectable
even after revocation. No operation implicitly replaces the immutable task.
Goal replacement must call `abandon` to retire this instance, then explicitly
construct a new task. Do not infer retirement by parsing an invalidation reason.
Accepted completion is terminal through pause, invalidation and bad clocks;
explicit abandonment may retire it. Status retains the exact final verification
checkpoint and rechecks source integrity. Later disputes lower freshness and
produce a diagnostic without rewriting the historical completed outcome.

DispatchIntent binds run/task/version, plan/version, epoch, stage, skill/version,
and StepProposal (logical ID, exact before, action, expected position, wait).
It explicitly advertises `grants_dispatch_authority=False`. Only exact equality
with the single outstanding intent can settle it. Duplicate identical settlements
are idempotent; conflicting duplicates raise. Logical IDs cannot be reused across
epochs or legs. RunStatus always has `lease_owner=None`; status freshness is
computed at caller clocks and never changes a stale plan's binding.

## State and planning

| Trigger | Result and gate |
| --- | --- |
| explicit start | Fresh origin, retained sources, guard and budgets; submit outbound planning |
| planning | No intent; one physical planner call; immutable request binding |
| successful poll | Exact candidate binding and accepted skill v2; retain plan, create stage, admitted |
| propose | Recheck evidence/generation/epoch, return one intent, executing |
| exact settlement | Record memory, derived progress and conservative budgets; remain admitted or stop |
| outbound completed | Retain waypoint, submit fresh return request at its current revision |
| return completed | Verify both legs, retained start/waypoint/final, current epoch, no pending action; completed |
| pause/takeover | Advance epoch, cancel planner applicability, destroy active stage; paused/interrupted |
| unknown side effect | Preserve pending intent, unknown; never resume automatically |
| explicit continuation | Fresh guard and unchanged route checkpoint, original history/budgets; new epoch, then remaining-route plan or verification-only path |
| abandon/replacement | Retire memory and planner, no new proposals; retain unresolved result context |

Planner submit/poll/cancel is reused directly. Plan IDs/versions are generated
monotonically per instance. The immutable PlanningRequest contains current facts,
original start, waypoint, last action/disposition, progress/stop reason and remaining
budgets. Expected stage and exact remaining distance are derived from history.
Polling compares the original binding with current session/revision/epoch; any
changed observation or authority generation invalidates applicability rather than
rebasing a response. Provider failures/timeouts stop; no automatic planning retry.
If the stopped leg already has all its credited steps, continuation constructs a
fresh verification-only MovementStage and checks it without a planner request or
intent. Its completion either ends the return leg or triggers a new full-distance
return request after outbound. Never submit distance zero or reset per-leg budgets
to obtain a plan; the existing planner rejects zero-distance/zero-budget requests.
Cancellation may leave a physical provider call running: reuse the port and honor
its occupied slot and reserved accounting. Late calls can change accounting only.

All original budget ceilings persist. Remaining task and per-leg proposals derive
from history plus an outstanding intent; turns use original start; wall time
includes planning and pauses. Planner accounting comes from the existing port.
Exhausted budgets stop without another request or intent. Progress and overshoot
remain separate; reaching a coordinate does not imply accepted task completion.

An unresolved intent also has a passive wait deadline: publication time plus its
bounded `wait_seconds`. `poll` and `settle` check expiry at `now >= deadline`
before admitting any outcome. Every other valid mutating API also checks expiry
before its own revocation, so a pause at the deadline cannot change the cause.
Expiry revokes applicability to unknown and retains
the pending intent. A late explicit non-delivery can release it without credit;
other late outcomes remain unknown. An observed turn overshoot within the wait
retains verified progress as budget exhaustion; a wall-overdue result beyond the
wait is unknown, with raw displacement retained but no new credited progress.

## Revocation and continuation

Pause while planning cancels the call. Pause after intent publication cannot
assert that no action was delivered. Retain that unresolved intent and charge it.
An exact late `not_dispatched` or `rejected` result can resolve non-delivery without
credit; then explicit continuation may plan anew. Any late returned/dispatched/
unknown result remains unknown with no newly credited progress and prevents
continuation. A new observation cannot reconcile that unknown by itself. Session
change and source dispute stop the task; invalidation never imports another
world's origin. Abandoned instances cannot resume.

Detached non-delivery settlement belongs to the supervisor: compare the complete
saved intent and exact result ID/before, require retained same-session references,
and require any after-reference to be ordered and at the same position with zero
or absent displacement. Append exactly one charged, no-credit RouteAttempt without
calling or rearming the destroyed stage. Malformed/conflicting results do not
release pending state. This is a trusted caller assertion of non-delivery, never
an inference from a later observation. Abandoned runs may retain settlement audit
data without recording into retired memory or becoming resumable.

The first revocation of an outstanding intent determines whether its known cause
was operator pause/takeover. Later pause calls cannot promote a non-operator
revocation into the non-delivery readmission exception.

The first returned zero step stops. Store its relevant observable signature:
route checkpoint, direction, movement binding, pause/boundary/category, visible
creatures and selected neighbor's visibility/terrain/furniture. Continuation
requires current normal-play guard success and a concrete relevant signature
change; timestamp/revision/frame bytes/model text alone do not qualify. Explicit
non-delivery also requires a relevant change unless it was an operator revocation
whose explicit continuation resolves that known cause. Source integrity, route
continuity and budgets always apply. Repeated equivalent no-progress signatures
remain rejected; bounded attempts prevent unlimited differing retries. This is
a conservative cardinal policy, not a generic learned expectation monitor.

## Evaluation and maintenance

Expose an immutable accounting snapshot from the original port and bounded
action/decision events compatible with RunRecorder. At export, merge one planner
snapshot with supervisor events in elapsed-time order. Use unknown measurements
with missing reasons; do not invent provider cost, useful-action credit, harms or
native dispatch. Caller/independent assessor supplies manifest and final outcome;
the supervisor does not self-certify native effectiveness. Tests instantiate the
real RunRecorder and validate the composed synthetic artifact.

Reuse these cohesive components instead of a generic behavior-tree/agent framework:
our missing capability is this bounded route state machine, not a new parser,
scheduler or transport. Revisit if multiple skills require shared branching.
Review source/contract/diagram drift on supervisor or controller integration;
#36 must test the lease and receipt mapping before connecting this passive API.

The 2026-10-17 targeted currency scan found no material change beyond the existing
[tiered](../research-tiered-gameplay.md) and [monitoring](../research-outcome-monitoring.md)
reviews. Recova (Oct 1 preprint) separates recovery and verified restoration before
resumption ([primary abstract](https://arxiv.org/abs/2610.01178)); this supports the
explicit readmission gate as a design inference, not evidence of CDDA performance.
No learned recovery or new model tier is justified by this bounded slice.

## Allocation and acceptance

Lead owns this brief, shared skills/history migration and its tests, docs,
integration, PM, final verification and publication. After independent interface
review and a checked shared checkpoint, one clean-context worker in a project-local
worktree owns only `harness/gameplay/supervisor.py` and
`tests/test_gameplay_supervisor.py`. No shared runtime, source overlap or service
edits. Explorers and reviewers run read-only in parallel. Lead takes back after
two failed repairs or ownership drift. Provisional M/Medium 3–5 focused sessions;
re-estimate after brief review, not from elapsed model time.

Independent clean-context interface review on 2026-10-17 found two gaps, now
resolved above: complete-leg verification must bypass zero-distance planning,
and revoked non-delivery needs detached settlement after stage destruction.
Final review found no remaining blockers. Retain M/Medium, 3–5 focused sessions:
shared migration, supervision, adversarial review and publication are cohesive
steps with source-integrity and cancellation risks; no native lane is added.

Test real retained evidence, memory, planner, skills and recorder composition:
both legs/fresh handoff; partial outbound/return continuation without replay;
full displacement followed by guard failure; stale/cancelled/late plans; pause
during planning and pending intent; exact/duplicate/conflicting result binding;
unknown side effects; session/epoch/source changes; prompts/threats/capacity;
equivalent nonprogress readmission; cumulative primitive/leg/turn/wall/planner
budgets and overshoot. No fixture may claim native/model efficacy or dispatch.
Run focused then common checks, independent clean-context code/test/contract review,
diagram render and visual inspection. Publish a protected exact-head PR and verify
merged-main CI before closing #35 and updating #22/#36. Preserve evidence/saves and
remove only owned branches/worktrees/processes. Record failures and unresolved
limits in a dated acceptance report; do not call the active goal complete early.

---
owner: lead
status: active
review_trigger: Gameplay interfaces, supported observations, model adapters, budgets or evaluation criteria change
---

# First gameplay slice — waypoint and return

Design for implementation under [#17](https://github.com/CVX-Hull/cdda-player/issues/17).
Typed gameplay/1 records and the passive bounded evidence adapter are implemented
under [#32](https://github.com/CVX-Hull/cdda-player/issues/32). The bounded injected
planner port is implemented under #34, skills/native predicate acceptance under
round009, and passive supervision/remaining-route continuation under round010.
Round012 connects service/controller execution to an external active-chat player.
Comparative model evaluation and general autonomous survival remain separate work.
[Architecture](../architecture.md) and [protocol](../protocol.md) are authoritative
about implemented behavior; the [foundation acceptance](../acceptance/2026-10-17-foundation-implementation.md)
separates portable evidence tests from native-v2 boundary probes. The
[research proposal](../research-tiered-gameplay.md) supplies evidence and alternatives;
its broader examples are not capabilities of this slice.

The proposed [outcome-monitoring contract](outcome-monitoring.md) addresses later
semantic tasks and escalation. It does not replace this slice's exact waypoint
predicates or add a dependency to its baseline acceptance. The
[evaluation brief](../changes/007-recovery-evaluation-monitoring.md#waypoint-experiment-protocol)
predeclares its comparison protocol; live provider and trial execution remain #24.

## Owner outcome and boundaries

Ask the agent to reach a nearby waypoint and return to its starting tile while
watching its goal, progress, deliberation and corrections. The first task is one
cardinal outbound leg of 1–4 tiles, then the reverse leg, on the same z-level.
The operator can specify the direction/distance; otherwise the strategist proposes
it from the current frame and visible adjacent terrain. No off-screen destination
or complete route is inferred. Each next tile must independently pass admission.
This tests two-stage planning and retained progress, rather than wrapping a single
keypress in an autonomous-service claim.

The origin is the session-relative avatar position at task admission. The waypoint
is a displacement from that origin, not an absolute world coordinate. Visiting it
must be proved before returning; simply staying at the origin is not success.
Unknown route cells may stop the task. No detours, doors, item pickup, combat,
vehicles, vertical movement, sleep, crafting, long waits or automatic exploration.
This bounded benchmark is not a survival policy and makes no trap/damage guarantee.

Start only by an explicit run request after observation and operator resume. Merely
recording a goal, starting the service or restoring a journal must never start play.
Pause revokes the current execution epoch, not verified task history. Resume restores
transport permission only. Explicit `continue(task_id)` creates a new execution epoch
after fresh normal-play evidence matches the last verified checkpoint, in the same
world/session, with no unresolved action. It replans only remaining work. Otherwise
continuation is rejected; the operator may abandon the task or create a new one.
Previously verified waypoint history is retained and must not be replayed merely
because an epoch changed. Service/game restart does not resume tasks from a journal.

## Responsibilities and handoffs

### Dedicated player sub-agent

![Current player responsibilities: the dedicated player proposes plans, the service validates and executes, and you retain Pause.](../diagrams/player.svg)

Solid arrows show responsibility and feedback, not independent model tiers.
[Editable diagram](../diagrams/player.mmd). Current behavior is specified in the
[protocol](../protocol.md#integrated-gameplay-lifecycle).

The integrated runtime uses one dedicated player sub-agent within the active
Codex chat. The lead owns task admission, shared runtime, supervision and final
verification; the player reads bounded retained observations and proposes the next
stage. The service validates candidates, checks fresh evidence and executes through
its controller lease. Planning is a data interface, not permission to send raw game
inputs. The player does not edit code/saves, operate native UI, resume transport or
launch another game. Its working context contains gameplay evidence rather than
engineering history. The lead can answer the same planning interface when needed;
there is no automatic player fallback.

The [current protocol](../protocol.md#integrated-gameplay-lifecycle) owns the runtime
contract, deadlines and accounting limits. The
[integration brief](../changes/012-integrated-player.md#player-arrangement) records
the decision, and [round012 acceptance](../acceptance/2026-10-18-integrated-player.md)
records the implementation and native evidence. The user chose
active-chat planning without a separately billed model API. A dedicated role does
not imply a cheaper model, OS isolation, independent persistence or measured token
cost. Losing the player must stop on a bounded deadline. A separate Codex session
is deferred until an independently managed conversation/lifecycle is needed.
Revisit this choice when native acceptance, latency, context retention or permission
needs provide contrary evidence. Ordinary controller/native guards remain enforced
even though sub-agents inherit the session's tool permissions.

### Execution boundaries

Use the [logical feedback diagram](../research-tiered-gameplay.md#proposed-system-who-decides-and-how-feedback-returns).
One process owns dispatch. A model call can run outside the controller lock so pause
and observation remain responsive; dispatch is stopped while planning. No second
model, action producer, generic agent framework or behavior-tree engine is required.

The controller owns an atomic run lease `(task_id, execution_epoch, owner)`, shared
by every HTTP/CLI/model ingress. Start acquires it only while command/control queues
are empty and the controller is reconciled; simultaneous starts have one winner.
Planner primitives must present the live lease as well as observed native authority.
External `key`, `action` and `walk` reject while the planner owns the lease; the
operator first takes over with Pause. Already-queued external commands retain their
admission epoch and cannot run after a new lease is acquired. Pause/takeover revokes
the lease before returning; queued planner commands recheck it at dispatch. Never
hold a command lock across a model call. Observation/status remain available, while
recovery input follows its separate explicit operator contract. Transport resume
does not create a lease. The controller rechecks the lease before publication;
the native final authority gate is the input commit point. A later Pause cannot
reverse an input already committed to the engine.

| Component | Input → output | Ownership and limits |
| --- | --- | --- |
| Strategist adapter | Evidence packet + task + implemented capability descriptors → candidate next stage or stop | One capable model initially; no controller/filesystem access through its tool interface; returns data, never executable code |
| Supervisor | Candidate + current evidence + control epoch → admitted stage or rejection | Sole run state machine; budgets, stage progression, stale-candidate rejection and feedback routing |
| Skill executor | Admitted stage + fresh observation → one primitive candidate and expected displacement | Reviewed cardinal movement; no direct bridge access, no unbounded macro |
| Controller | Primitive bound to session/revision → transport result | Reuse serialization, pause, expiry and reconciliation; only this component writes gameplay requests |
| Evidence store | Observations and action outcomes → bounded immutable evidence references | Separates measured facts, historical facts and interpretations; never supplies command authority |
| Spectator | Public run status/events → goal, stage, verified progress, next check and stop reason | Shows concise reasons and uncertainty; does not expose private model reasoning |

The existing multi-step `Controller._walk` is reference behavior, not a hidden loop
for the supervisor to call blindly. Extract/reuse its guard and displacement checks
so the supervisor sees every primitive outcome. Keep the current CLI walk contract
until an explicitly reviewed migration; its `stopped` result can contain all requested
steps and cannot be mapped to zero progress or automatically retried.

## Versioned records

Internal Python records, schema version `gameplay/1`; this does not by itself change
the native wire version. Define typed records at component boundaries and reject
unknown versions, fields outside the schema, invalid enum values and oversized input.
Prefer the existing JSON Schema tooling for serialized candidate validation and
standard-library typed records for internal data. No generated executable schemas.

| Record | Required content and invariants |
| --- | --- |
| `TaskSpec` | `task_id`, kind `waypoint_return`, world-scoped native session, origin `[x,y,z]`, direction, distance 1–4, target, task version, budgets, originating operator request. Target must equal origin plus declared displacement. Stable across explicit continuation epochs; no arbitrary natural-language completion predicate. |
| `EvidenceRef` | Immutable observation ID, native session/revision, native timestamp and local monotonic receipt time, turn, frame path/hash, boundary kind, visibility allowlist version. A missing/failed frame is missing evidence, not the last frame relabeled as new. |
| `EvidencePacket` | Task/plan/stage IDs, current evidence reference, retained start/waypoint references, last primitive ID and transport disposition, observed displacement, stop reason, remaining budgets, bounded facts and separately tagged interpretations. |
| `SkillDescriptor` | Stable skill ID and version; supported task/stage kinds, contexts and action bindings; observable predicates, allowed primitives, postconditions, stop rules and maximum budgets. Registry advertises only implemented/accepted skills. |
| `PlanCandidate` | Candidate ID, task/plan versions, operator control epoch, original evidence session/revision, stage `outbound` or `return`, direction/distance remaining, skill ID/version, concise reason. No credentials, native paths, mutable code or arbitrary tools. |
| `PrimitiveResult` | Unique action ID; before/after evidence references; transport disposition `not_dispatched`, `dispatched`, `returned`, `rejected` or `unknown`; observed displacement separately; reason. An unobserved side effect remains unknown. |
| `StageResult` | Stage ID/version; disposition `completed`, `blocked`, `interrupted`, `budget_exhausted`, `failed` or `unknown`; verified steps/displacement, evidence references, and pending action ID if any. Progress and disposition are independent fields. |
| `RunStatus` | Task/plan/stage IDs, execution epoch, state, active model/configuration and skill version, progress, remaining budgets, next check, last public reason, lease ownership/pause/freshness and evidence references. Model timing/cost is additional telemetry, not completion proof. |

Implemented module ownership: `harness/gameplay/contracts.py` and `evidence.py`.
The bounded injected `planner.py` and passive remaining-route `skills.py` are implemented.
The skill proposes/evaluates one step; a new instance derives the remaining route
from retained settled history. It cannot dispatch or automatically resume.
See the [current skill contract](../protocol.md#passive-bounded-movement-skills).
The passive `supervisor.py` composes these components. `harness/runtime.py` owns
service lifecycle, external-chat handoff and production controller integration;
it sits outside the passive gameplay package. Imports must not reverse that boundary.

## Admission, progress and completion

Every primitive requires a matching successful frame, current session/revision,
normal-play boundary (not just the reused `DEFAULTMODE` category), active unpaused
run and fresh observation. A local maximum observation age of three seconds is an
initial admission ceiling, aligned with today's stale display; elapsed age never
refreshes a revision. Re-observe and re-plan when age or authority fails.

Use the existing visible-creature list (any creature stops), CLEAR adjacent terrain,
empty furniture and allowlisted surface checks. Required arrays/types must be valid;
missing evidence fails closed. The movement action must be registered and actually
have a usable binding; native rejection is a result to record, not permission to
try alternate keys. Skill registry support cannot make an unsupported action valid.

After each action, check the same session, normal-play boundary, expected exact
unit displacement and matching frame. Append verified progress only once for that
action ID. Fresh changed position is not evidence that an unrelated unknown action
succeeded. A stage completes only when its final position is verified and its
postconditions hold; a stop may still contain partial or full displacement.

The outbound completion reference proves the waypoint visit. The return completion
reference proves the later origin visit in the same task/world-scoped session, with
no unresolved primitive. The overall result is `completed` only if both stages have
verified evidence and the final observation belongs to the currently authorized
execution epoch. Earlier verified progress can survive an explicitly continued epoch;
an abandoned task cannot complete. A creature appearing on the final tile can produce full
displacement with a blocked result; retain the evidence and do not claim success.

| Predicate | Evidence available today | Gap/disposition |
| --- | --- | --- |
| Position and unit displacement | Native-v3 relative position and session rotate on world entry/exit, including same-process reload | Supervisor rejects session replacement; runtime checks controller lease/session before dispatch |
| Next tile and creature stop | CLEAR neighboring terrain/furniture; UI visible-creature list | No farther route knowledge; missing or stale values block |
| Matching frame, turn and authority | Native frame/status/session/revision/turn; passive adapter validates retained originals and receipt age | [Round 009](../acceptance/2026-10-17-bounded-skills.md) exercises actual retained native frames; fault lanes are separate |
| Ordinary play rather than running activity or raw error | Native-v3 positive boundary discriminator; category and `in_game` alone remain insufficient | The passive skill requires normal_play; recovery controls remain separate |
| Damage, trap absence, safe water or inventory | Not structured guarantees | Excluded from deterministic predicates; no new exports selected for this task |

Thus #19 uses the implemented passive observation adapter and negative-case
validation, with bounded native pipeline acceptance recorded in round 009; no broad map or inventory exporter. Native boundary metadata is owned by #7 and shared explicitly.

## Supervision and correction

States: `idle → planning → admitted → executing → verifying`, then the next
primitive, `planning` at a stage boundary, or a terminal/suspended result. The model
cannot directly enter `executing`. There is at most one unresolved primitive and
one admitted stage. No gameplay is dispatched while a model call is pending.

Each task execution has a monotonic control epoch. Pause, takeover and goal replacement
revoke it; service restart restores no authority. A terminal stop ends
the current admission, and explicit continuation requires a new epoch. Native
session changes invalidate task applicability while historical evidence remains
retained. A candidate must exactly match the task/plan/epoch and original observed
session/revision, as well as the current skill version. Re-observation may establish
that these still match; it must not substitute a newer revision into old intent.
Discard late results and record why. A plan's verified history can survive expected
revisions, but any newly admitted stage is grounded in its own fresh evidence.

Continue locally only after verified expected progress. Stage completion requests
a new strategic stage decision using the retained waypoint evidence. An obstacle,
prompt, creature, unknown prerequisite, unexpected displacement or first verified
no-progress result stops the skill immediately. Send the evidence packet to the
strategist for explanation/replanning; this slice permits stopping or re-proposing
the remaining original route only after fresh admissible evidence. No detour or
automatic retry. A second equivalent non-progress admission is rejected by the
supervisor unless new evidence resolves the recorded blocker.

Timeout/unknown side effect freezes transport and the run. Reconciliation follows
the current protocol; it does not erase uncertainty about task success. Pause and
takeover bypass all planning throttles. Replanning does not resume a revoked run.
Do not replay a complete skill to recover from partial progress.

## Initial budgets and model choice

These are conservative configuration defaults to test, not measured optimal values:
at most eight primitives per run, four per leg; at most 32 game turns from admission;
120 seconds of task wall time; ten planner calls; at most 30 seconds per call.
Check every primitive and at every stage handoff. A model call timeout stops the
run; a late result cannot rearm it. Budgets include planning time and never reset
because a stage is replanned or explicitly continued. Paused time still counts in
this first slice; an exhausted task must be abandoned, not renewed by continuation.
Use monotonic host time and native turn deltas; record
overshoot from an already-dispatched engine action rather than promise instant stop.
No per-primitive wait may exceed the controller's existing 15-second ceiling.

Each separately billed network provider additionally requires explicit model identifier/version,
context/output limits, known pricing or a conservative reservation mechanism, and a
positive operator-approved per-run spend ceiling. Reserve the worst permitted cost
before each call; stop if cost cannot be bounded, credentials are absent or provider
configuration is incomplete. Zero/absent spend configuration disables API calls.
This round selects no paid provider and authorizes no spending. The adapter contract
must support deterministic fixtures for tests and a real capable model for later
native acceptance; fixture success is not model-performance evidence.
The selected external-chat arrangement instead makes no API calls: its enforced
request/deadline/gameplay bounds and explicitly unmeasured model usage follow the
[player integration contract](../changes/012-integrated-player.md#player-arrangement).

Role separation is independent of model separation. Task complexity may justify the
same capable model at any decision point. Smaller models, streaming execution during
planning and additional routing are conditional work in #25, not prerequisites.

## Evidence retention and evaluation handoff

Retain immutable task start, waypoint, terminal/failure and primitive before/after
frames before the bridge's 120-frame cache evicts them. Store them beneath the
project session directory with hashes and references. Limit each run to 32 distinct
frames and 64 MiB of copied evidence; stop before a dispatch whose required evidence
cannot be retained. Do not delete saves or automatically erase existing accepted
evidence. Keep a bounded record of current facts plus these references; summaries
are interpretations and never replace source evidence. Session restart invalidates
current facts; contradiction invalidates the affected fact and dependent candidate.

#18 freezes the evaluation protocol before #24 runs it: capable model selecting
primitives versus the same model using skills, then optional same-model role/effort
separation. Keep starts, evidence, action/time/spend guards and configuration matched.
Call count is a measured outcome; use a declared ceiling feasible for both arms
(the ten-call default permits all eight primitive decisions). Pilot time/spend
limits on development cases before freezing them, so one arm is not structurally
unable to finish. A fixed user-budget stress test is a separate reported condition.
Explicitly continued tasks can complete for the operator, but any human intervention
is recorded and excluded from the uninterrupted autonomous-success metric; report
assisted completion separately. Never silently discard interrupted/censored runs.
Use distinct development and held-out scenario families and repeated trials; include
failed/censored runs, uncertainty and cost of all verification/recovery/router calls.
Predeclare sample counts, seeds where supported, stopping rules and practical outcome/
cost thresholds in that issue before spending. No model-tier superiority threshold
or sample size is fabricated in this design-only round.

Required scenarios include straight clear route and return, blocked/missing neighbor,
creature appearing, prompt/activity boundary, full displacement followed by stop,
goal replacement, stale candidate, pause/takeover during a model call and primitive,
unknown timeout, restart, contradictory memory, exhausted budgets, binding rejection,
missing frame and no-progress repetition. Unit/contract replay tests prove software
responses only. #8 verifies native control; #24 verifies actual windowed gameplay and
matched model outcomes. #23 verifies readable ordinary, paused, stale and slow states.

The [bounded memory increment](../changes/006-recovery-memory.md) implements passive
TaskMemory over EvidenceStore. Current records, invalidation, retention ceilings
and limitations are owned by the [protocol](../protocol.md#passive-task-memory).
Round010 adds [passive supervision](../protocol.md#passive-waypoint-supervision)
and skill continuation. Model tiers, service/controller integration and a native
waypoint-and-return outcome remain distinct future work.

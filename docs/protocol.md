---
owner: maintainer
review_trigger: Native bridge, controller, input, observation or skill change
status: active
---

# Bridge and guarded-play contract

Protocol version: 3.

This is the detailed current contract supporting [architecture](architecture.md).
Authority rules are [S-PROTOCOL](engineering.md#s-protocol-command-and-observation-authority).
Portable checks do not prove native engine behavior.

Unsupported versions and alternate response shapes are rejected. Startup validates
stored admissions, claimed requests and any response before restoring uncertainty;
it never converts old records. A dispatched response without its current-format
input identity blocks startup instead of fabricating a synthetic request. An offline
migration must preserve uncertainty and cannot grant authority or replay inputs.
See [coordinated migration](runbook.md#coordinated-migration).

## Controller run ownership

The in-process controller API exposes `acquire_run(task_id, execution_epoch,
owner, *, expected_session, expected_revision)`, `execute_run(lease, *, action,
expected_session, expected_revision, logical_action_id, deadline_monotonic,
timeout=None)` and `release_run(lease)`.
A frozen RunLease belongs to exactly one controller and native session; only the
exact returned Python object authorizes input. Descriptive fields or a JSON copy
cannot reconstruct it. The public status `run_lease` is null or descriptive
`task_id`, `execution_epoch`, `owner`, `session`; it never grants authority.

Acquisition is explicit, nonblocking and has one winner. It requires no active or
queued ordinary/control writer, live lease, pending effect or native inbox, plus
reconciled, unpaused, fresh successful normal-play evidence matching the supplied
session/revision. It rotates native authority and admission generation without
observing, resuming or dispatching. Historical unknowns remain historical unknowns;
new ownership cannot establish the outcome or continuation of an older task.

Ordinary external key/action/walk/resume reject while leased. Existing HTTP/CLI
input reaches this same controller gate; it cannot supply or obtain a capability.
Observe/status, record-only goal and Pause remain available. The viewer displays
run ownership and disables ordinary input/Resume until takeover. A model call
never holds controller locks. An explicit gameplay start/continue connects the
service supervisor to a lease; service startup and transport Resume never do.

A leased call submits one semantic action, using existing native-v3 observation
and input checks. The original command admission generation and exact live lease
are checked around queueing/preflight and immediately before atomic publication.
Every walk step uses its original entry generation. Pre-takeover or pre-acquisition
queued inputs cannot become current merely by waiting. No stale expected revision
is silently refreshed.

Pause and release revoke before returning; release requires the current capability
and also pauses. Recovery, native takeover/session change, a paused native
observation, transport failure and shutdown invalidate ownership. Resume does not
restore a lease. Startup restores no task or capability. Native token validation
remains the final input commit gate; an already committed action cannot be undone.
`execute_run` returns an envelope containing the logical action ID, exact native
`request` or null, `result`, `published`, and original terminal
`received_monotonic` or null. Preflight Observe is not an action receipt. The
absolute monotonic intent/task deadline is checked after queueing/preflight and
under the publication lock; it bounds both exchanges and the native deadline.
`observation_snapshot()` returns a copied current observation and original first
receipt clock. Reading a snapshot does not renew its freshness.

## Integrated gameplay lifecycle

`harness/runtime.py` connects the passive gameplay package to the controller. The
service constructs one GameplayRuntime but starts no task until an authenticated
explicit request. One run worker owns the supervisor, evidence store, external
planner inbox and exact lease. Evidence is retained under the project session
journal directory. Restart restores neither task execution nor authority.

Authenticated `POST /api/gameplay` uses the same loopback host/origin/token and
4096-byte request limits as operator commands. Fields must match exactly:

| kind | Fields besides kind |
| --- | --- |
| start | direction, distance (1–4), expected_session, expected_revision |
| continue | run_id, execution_epoch, expected_session, expected_revision |
| abandon | run_id, execution_epoch |
| planning_request | none |
| plan | request_id, candidate (gameplay/1 PlanCandidate object) |

Start constructs the waypoint task from the observed origin with existing bounded
budgets. Continue preserves task/history/original budgets, requires a fresh same-world
checkpoint and no unresolved effect, and creates a new epoch/lease. Neither resumes
transport. Completed/stopped tasks remain inspectable until explicit abandon;
starting another task requires abandonment and worker exit. Recording goal text
still does not start or replace a task. Ordinary Pause immediately revokes controller
authority without waiting for a model/native exchange; serialized supervisor
invalidation follows. Completion releases the lease and leaves transport paused.
Recovery keeps its existing exact-generation contract; no extra preceding Pause
changes the caller's supplied generation.

Runtime responses contain status `accepted` or `rejected`, a gameplay snapshot and
an error when applicable; planning_request additionally returns its pending request
or null. HTTP ingress errors retain ordinary error-only responses and status codes.
An accepted asynchronous lifecycle request is not a completed task; inspect status.
The CLI exposes gameplay-start, gameplay-continue, gameplay-abandon, gameplay-request
and gameplay-plan; see the [operator procedure](runbook.md).

The waypoint planner is a dedicated sub-agent in this active Codex chat. The lead
admits tasks and owns runtime/verification. This planner reads bounded visible
evidence and returns candidate data only; it does not send raw game inputs or
manage the game. The same external planning interface can be answered by the
lead, with no automatic fallback. Missing planner, deadline, invalid plan or changed
evidence stops visibly. No separate paid API is connected. A separately admitted
campaign operator uses the external operator procedure below; it cannot send
ordinary inputs while a waypoint run holds its lease.

Each external request contains request_id, deadline_ms and decoded ProviderInput
`input` (task, packet, skills, binding, public_context, admission_monotonic). One
request accepts at most one candidate; duplicates, wrong IDs, cancelled and late
answers reject. A pending observation may age while reasoning. Before admitting
that answer, runtime obtains fresh Observe and explicitly revalidates equivalence:
same session/revision/turn/position, complete visible scene, actions, boundary/control
identity and retained frame hash, with no intervening invalidation. It records the
old/new evidence, preserves the original candidate binding, and reruns fresh guards.
Changed evidence stops and requires explicit continuation/replanning; no timestamp,
revision or deadline is silently rewritten. Input evidence still expires at three
seconds. Status reports an aged planning source as stale without invalidating it
merely for age; disputes still revoke evidence authority.

Every intent reserves evidence capacity before dispatch, validates its original
absolute deadline and real lease, and maps to exactly one native action admission.
Only attributable successful retained after-evidence can earn progress. Known
nonpublication is not_dispatched; exact rejection is rejected; uncertain publication,
missing/malformed frame, timeout or changed-world result remains unknown. Observe
reconciliation cannot retrospectively turn an unknown action into success. Preserve
raw failure receipts and reservations for unresolved effects; never replay.

`/api/status.gameplay` is null or contains run_id, TaskSpec `task`, RunStatus `run`,
`planner`, and last_receipt. Runtime supplies actual descriptive ownership, pause,
next check and historical progress; status never authorizes an input. Planner shows
external_chat, pending_request_id, deadline_ms and usage_known=false. Receipt summary
shows logical_action_id, native_request_id, disposition and reason. The spectator
shows task, stage, progress, next check and stop reason, with evidence and unknown
cost details behind disclosure; no private reasoning transcript is exposed.

## Transport and state


The game enables the bridge only when CDDA_HARNESS_DIR names an existing private
directory. Version 3 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. Each channel admits one live request at a time; the host holds a
process lock for both writers. Gameplay and recovery retain separate identities. Requests carry protocol, unique id, session, expected revision,
kind and payload. Size is bounded to 4096 bytes. World entry and exit replace the
session, including a same-process save/reload; relative coordinates belong to that
world lifetime. Stale session/revision commands are rejected, never replayed.
Producer, controller, discovery, CLI, viewer and evidence validation require v3.
Older and unknown versions are rejected; there is no fallback.

Commands: observe, key, action, pause, resume. Observe is side-effect-free in
gameplay terms. Key is one ASCII character or named navigation key, never an
unbounded string/macro. Action chooses a binding registered in the active input
context. Registered actions may have no usable single-key binding in the current
input mode; such a request is rejected. An advertised action is not a guarantee
of an executable binding. Pause prevents further remote inputs; resume is explicit. Native human
keyboard/button input latches takeover and increments revision. Mouse motion
alone does not pause. A separate pause sentinel may interrupt a pending host
routine even while the serialized command is waiting; it cannot reverse an
already dispatched engine action. Every input-authorizing request also carries
`authority: {controller_boot_id, counter}`. The host atomically publishes and
fsyncs the token in `authority.json` before Pause (including repeated Pause),
startup retirement, shutdown and observed takeover. Admission and revocation share
the host data lock. The native gate reads the token again immediately before
committing input; a claimed request with an obsolete, missing or malformed token
is rejected. Pause after that commit cannot undo input. Native control generation
and the host token are separate authorities; controller run leases use this same
revocation mechanism.

The SDL input loop pumps normal events while polling. RAII scopes span
`input_context::handle_input`, including retries and nested contexts. An explicit
marker at ordinary avatar input distinguishes normal play; deathcam, unknown
DEFAULTMODE callers, activity polling and raw debug prompts cannot inherit it.
The pinned common direction helper marks only its own `handle_input()` wait as a
menu, preserving DEFAULTMODE for native binding lookup. This marker activates only
in-game with no enclosing scope or active direction query; classification requires
the stack still be empty when that exact DEFAULTMODE input scope opens. Nested
contexts and callbacks after the wait cannot inherit its permission. The ownership-
aware RAII marker clears during return/unwinding. It exports no structured scene.
Activity and debug scopes override enclosing input. Incidental animation polls are
unscoped and cannot dispatch or acknowledge commands. An explicit lifecycle flag
around main.cpp's do_turn loop gates gameplay metadata. Remote input_event delivery includes an
SDL/ImGui adapter for key/text events without sending OS events; native events
are separately observed for takeover.

Each observation has a required `boundary` object: `kind`, nonempty `id`,
nonnegative `control_generation`, `recovery_operations` (zero or one operation), and
`interrupt_request_id` (nonnull only at an owned interruption confirmation). Boundary instances change with context,
session and native takeover, rather than every repaint. The supported matrix is:

| Kind | Observe | key/action/resume | Structured scene |
| --- | --- | --- | --- |
| `normal_play` | Yes | Fresh matching frame and authority required | Player-visible allowlist |
| `menu` | Yes | Fresh matching frame and authority required | None |
| `activity_poll`, `debug_prompt`, `unsupported` | Yes at instrumented polls | Rejected | None |
| `interrupt_confirmation` | Yes at the owned rendered question | Rejected | None |

Menu classification is explicit in the native scope constructor; unrecognized
categories remain unsupported. A registered action is not permission to act at an
unsupported boundary. Recovery uses the separate channel below. Ordinary key/action/resume never
gains permission from a recovery operation. Native keyboard input remains available.

At an eligible rendered boundary the bridge publishes observation metadata and
PNG. Publication redraws the current UI and captures the window backbuffer
immediately before SDL_RenderPresent, checking boundary/session/revision provenance;
the older display-buffer screenshot helper omitted ImGui popup content.
PNG names are immutable session/frame-counter identities, with metadata
published after the corresponding atomic file rename. The viewer grants input
authority only after that image decodes and matches the latest session/revision;
old asynchronous decodes cannot restore a fresh label or authorize an old choice.
A command is dispatched at
most once within the live session; the next input boundary acknowledges that
the engine has returned to input, not that the intended gameplay objective
succeeded. Prompts and menus are valid outcomes and require new interpretation.
Unrecognized keys may leave the category unchanged. Long activities may not
yield promptly: host deadlines produce **unknown outcome**, freeze further
actions, and require observe/reconciliation. No automatic action retry.

Request lifecycle: published request.json → atomically claimed.json → dispatched
→ ready at the next eligible input boundary, or rejected before dispatch. A
unique id cannot execute twice within a game session. Requests carry a short
absolute expiry. On startup or timeout the controller revokes host authority and
writes the pause sentinel, then attempts an atomic rename of an undispatched request to a retired
file. If the game won the claim race, disposition is unknown until a matching
terminal response or expiry plus paused observation establishes reconciliation.
Never overwrite/retry an unresolved gameplay request. A new observe may restore
knowledge of current state but cannot prove the original objective succeeded.
World replacement never acknowledges an old-world action as successful. The host
retains unresolved input identities as unknown outcomes and in the journal. Before
publishing key/action/resume, it fsyncs a private durable admission under
`.runtime/bridge/admissions/`. A matching validated `ready` or `rejected` terminal response retires that request
admission. Definitive rejection is known non-dispatch; it does not resolve other
uncertain requests. Timeout, crash or world replacement leaves the admission for
restart recovery.
Reconciliation and a new host boot never silently erase or replay the old input.

All outcomes include request id, session, revision, category, pause state,
timestamp, frame reference and error/status. Revision tracks accepted remote
inputs and meaningful native input. Observations include age; a missing/stale
frame is visible. The bridge must not falsely acknowledge successful capture.
Frame metadata is published only after its PNG is atomically replaced. World
turn changes and context/action-set changes invalidate revisions too. TURN_DURATION
is fixed at zero for the MVP. Resume increments revision, requiring new command
authority. Planner commands carry the session/revision from the observation
used to choose them; fresh-observing cannot silently authorize a stale choice.

## Explicit operator recovery

`Controller.recover(kind, **payload)` is the local Python operator interface.
Authenticated loopback `POST /api/recovery`, explicit CLI recovery commands and
the spectator recovery panel expose this same operator-only boundary. Ordinary
`/api/command` and planner execution reject recovery kinds.
Recovery first pauses and revokes gameplay, then admits its own durable token.
The process lock outlives both writers; a nonblocking control lock prevents two
recoveries. Recovery never waits for the ordinary command lock. The data lock
serializes admission and revocation; shutdown revokes and waits for both writers.

Files are `control.json → control-claimed.json → control-response.json`, with
separate UUIDs, bounded native duplicate ledger and `control-admissions/` records.
An envelope has exactly `protocol: 3`, `id`, `kind`, `session`,
`control_generation`, `authority`, `created_ms`, `deadline_ms`, plus the operation's
fields below. Integer Unix-millisecond expiry is exactly creation plus 2000;
future creation has at most 1000 ms tolerance. Maximum request size is 4096 bytes.
No deadline extension, implicit refresh or automatic retry is permitted.

| Kind | Additional wire fields | Eligibility and delivery |
| --- | --- | --- |
| `request_interrupt` | None | Eligible activity poll advertises it; resolve registered native `pause`, preserving the engine's keyboard-interruption policy |
| `answer_interrupt` | `boundary_id`, `revision`, `frame`, `interrupt_request_id`, `choice` (`YES`/`NO`) | Exact owned rendered query; resolve that choice's active usable binding |
| `continue_debug_once` | `boundary_id`, `revision`, `frame` | Exact raw debug prompt; deliver one Space, never ignore future errors |

Python and HTTP callers supply `expected_session` and `expected_control_generation`.
Answers/dismissals also require `expected_boundary_id`, `expected_revision` and
`expected_frame`; answers add the owning `interrupt_request_id` and `choice`.
HTTP requests use exactly `kind` and the required fields above, with optional
positive `timeout` up to 15 seconds. They retain the ordinary endpoint’s Host,
origin, token, content-type and 4096-byte guards. Malformed input returns 400;
rejected/unknown/controller-error outcomes return 409; other terminal recovery
outcomes return 200. HTTP success reports delivery semantics only. The CLI uses
`--session`, `--generation`, and for prompt operations `--boundary`, `--revision`,
`--frame`; answers also require `--interrupt-request-id` and `--choice YES|NO`.
No surface fetches new authority to silently replace an operator’s decision.

The controller checks freshness and advertised operations. Native rechecks session,
generation, eligibility and rendered prompt evidence, then reads the host token
again at the final commit gate. Delivery latches Pause and increments native
control generation/revision. A later Pause cannot undo already committed input.

Only the specific cancellation questions invoked by harness-delivered native
pause gain interruption ownership. Generic YESNO questions do not. Nested unrelated
input or debug overrides that scope. Each owned question gets a new boundary ID;
returning from a nested boundary requires new matching evidence. Scene metadata
remains exclusive to normal play. Recovery is polled before ordinary requests,
even while an ordinary response is pending, after native input and Pause handling.

A control response has exactly `protocol`, `id`, `status`, `error`, `state`; `state`
is the ordinary current-v3 observation shape. `dispatched` is nonterminal.
`prompt_opened` requires an actual fresh owned confirmation frame.
`answer_delivered` and `dismissal_delivered` report input delivery, even if no new
successful frame is available. `not_applicable` and `rejected` report no applicable
operation or a failed gate. Host timeout is `unknown`; host failures are
`controller_error`. No status alone proves cancellation, error repair or task success.
Transport-only Pause preserves scene revision so recovery can validate the rendered
activity frame that informed admission. Actual input, takeover, resume and boundary
changes still invalidate authority. An activity can finish or reach an unrelated
prompt before claim; inspect the result and observe deliberately, without automatic
refresh or retry. [Native acceptance](acceptance/2026-10-17-native-recovery-planner.md)
separates production gameplay from injected timing and reply-loss probes.

The original gameplay response/pending identity is preserved. Control results may
update passive state but cannot resume gameplay. `control_pending` and
`control_unknown_outcomes` expose separate uncertainty; durable admissions outlive
bounded display history. A matching terminal result can retire only its own
admission. After timeout, only an explicit successful fresh observe after the
native deadline may reconcile the live control slot; passive status cannot rearm
it. Revoke, retire unclaimed work and reject unreconciled claims/active writers
before deliberately admitting another recovery. Keep historical unknown outcomes
and their admissions; reconciliation does not infer what happened or replay input.

Offline migration can preserve older unknown actions through
`historical-incidents.json`: exact `schema: "incident/1"`, `incidents` (at most 64).
Each record has `id` (1–128 chars), `channel` (`gameplay`/`control`), `source_path`
(project-relative under `.runtime/incidents/`, at most 1024 chars), `source_sha256`
(lowercase SHA-256) and `reason` (1–1024 chars). IDs are unique per channel. Startup
verifies containment, file existence, at most 1 MiB and hash, without parsing old
bytes. Invalid references block startup. These surface as `historical_unknowns`
and journal evidence, granting no authority, replay or inferred resolution.

## Designated campaign operator

The lead may designate one general-purpose sub-agent to choose and send ordinary
operator commands for a bounded campaign segment. This is an external operator
workflow using the existing authenticated CLI, not a new runtime supervisor or
RunLease type. The waypoint planner remains candidate-only. No runtime contract,
wire version, stored task format or automatic role restoration changes.

The lead owns source/release acceptance, finite admission, game/service lifecycle,
escalation and final verification. The designated operator owns ordinary decisions,
the charged capture sequence and visible-outcome assessment only for its named
segment. Its brief names the immutable source/native, allowed command and file
scope, actor identity, phase and cumulative limits, cleanup reserve and stop rules.
It may not launch processes, modify source/saves, publish work, start a competing
task, use debug advantages or silently extend a segment. Explorers/reviewers are
not input operators. Role instructions and recorded actor names do not isolate
tools or authenticate an agent to the OS.

Admit this mode only with no live waypoint lease, unresolved live request or
competing executor. Retained historical unknowns stay unknown. The controller
still checks current session/revision, frame, boundary and host authority for
every input; serialization does not identify which chat requested it. The lead
must not issue ordinary inputs or Resume while the player is assigned input.
Status, watching and emergency Pause remain available. Deliberate native inspection
or a new Observe decision uses the handoff procedure to avoid racing the player.

For handoff, request stop/Pause and have the operator finish its current tool call,
Pause, and return a source-linked checkpoint with no further command scheduled.
Verify that the agent turn and every retained execution handle are terminal, then
check controller status for no live request/recovery or run lease. Status alone
does not establish an empty external tool queue. Lead Pause fences remaining
pre-takeover requests at the existing generation/token checks; committed native
actions or activities may still take effect. Fresh Observe must show an interpretable
paused boundary before inspection or another actor is authorized. Unresolved or
unknown effects retain their normal reconciliation rules; never replay an input.

Returning input requires a new explicit bounded actor assignment, fresh evidence
and Resume by that actor. Preserve original history, consumed budgets and spatial
invalidation; no ownership, saved command or active model call is restored. A missing
or unquiesced operator, failed access/approval, corrupt accounting or unreadable
state stops further play. The lead may perform bounded ordinary recovery after
handoff using the established recovery procedure; user rescue is not the fallback.

Actor assignment/quiescence and campaign semantic limits are workflow controls.
They are not an exclusive external capability or a sandbox against a malicious
cooperating agent. The native/controller authority, Pause and in-process waypoint
lease retain their implemented guarantees. The [two-phase operator acceptance](acceptance/2026-10-18-campaign-operator.md)
records actual delegated input, paused inspection and fresh reassignment, following
a retained access failure. No broader survival reliability or unattended service
is implied by this procedure.



## Closed-loop play and observations


Use goal → bounded skill → one primitive → fresh observation → verification.
Start with movement, menu navigation and single actions. Movement routines have
a small step limit, require normal-game context, and stop on a prompt, no
progress, any visible creature, pause, stale revision or
transport error. Unknown information stops a routine instead of assuming safe.
Maintain observed facts with provenance/age; do not infer an unseen route is
clear. Structured movement fields are relative avatar position, current game
turn, the UI's visible-creature list, and eight neighboring tiles' terrain and
furniture identities only at CLEAR visibility. No item contents, unseen
creatures, absolute world position, or trap state is exported. Movement accepts
only a small known floor/ground whitelist without furniture. Damage has no
structured field in the first slice and is assessed visually by the planner;
no deterministic damage guard is claimed. The model chooses high-level objectives, while deterministic guards
handle immediate interrupts. VLA/robotics supplies architectural inspiration;
there is no reason to train a robot motor policy for a discrete keyboard game.

Measure verified primitive actions, model invocations, elapsed time, task
completion and harness failures. Compare single-step control and a guarded
routine on a repeatable safe route, with fresh observations in both. Do not
confound fewer model calls with better survival, or claim statistical superiority
from one short demonstration.

A guarded walk checks the next tile even after its final requested displacement.
It can return `stopped` with all requested steps completed if the next tile is
blocked. Read `steps` and the fresh observation; `stopped` does not mean no
movement occurred and must not cause an automatic retry.

## Passive gameplay records and evidence

[Contracts](../harness/gameplay/contracts.py) define eight frozen records:
TaskSpec, EvidenceRef, EvidencePacket, SkillDescriptor, PlanCandidate,
PrimitiveResult, StageResult and RunStatus. Serialized records carry
`schema: "gameplay/1"` and `record_type`; `to_dict`/`from_dict` reject unknown fields,
wrong types, unsupported enums, nonfinite numbers and contradictory completion
claims. JSON is bounded to 1 MiB. The injected planner below consumes these records;
the runtime above connects the passive planner, supervisor and bounded skill.
Broader task formation remains outside this [first slice](design/gameplay.md).

[EvidenceStore](../harness/gameplay/evidence.py) accepts only native-v3 positively
marked normal-play observations with a successful frame and the existing visible
scene allowlist. Its observation identity is the hash of session plus immutable
frame basename; a transport request ID is not a frame identity. It copies original
PNG bytes outside the evictable bridge cache, verifies hashes and records session,
revision, native timestamp, actual first receipt and `cdda-visible/1` provenance.
It checks bounded PNG signature/size and byte integrity, not image decoding; native
capture and viewer/native graphical acceptance own rendering quality.

At first ingestion, native wall-clock age must be -1000 through 3000 ms. Effective
age adds nonnegative initial lag to monotonic time elapsed since the original
receipt, with a three-second ceiling. Duplicate reads and reopening never renew
that receipt. Clock discontinuity, missing/corrupt source, unsupported boundary,
revision regression, contradiction or session replacement invalidates current
authority. A conflicting retained identity cannot become current again, including
when it was not the current frame; same-revision scene conflicts invalidate
retained peers. Transport-only Pause may produce distinct frames at the same
scene revision: `paused` remains immutable within one frame but is excluded from
cross-frame scene comparison. Actual scene/boundary conflicts still dispute peers.
Historical references remain verifiable but cannot authorize input.
Reopening starts without current authority or a dispatch reservation.

Each caller-owned task/run store has one writer, at most 32 distinct frames and
64 MiB, including existing files on reopen. Each image is at most 32 MiB. Before
dispatch, retain the before-frame and reserve one additional slot plus 32 MiB for
the after/failure frame. Consume or explicitly release that reservation; capacity
failure stops before dispatch and never deletes evidence to make room. The store
itself cannot dispatch. There is no automatic pruning, hidden-state augmentation
or synthetic replacement. Original evidence and bounded tagged interpretations
remain separate. A cross-session PrimitiveResult can retain an after-observation
only as unknown context with no attributed displacement. The real end-to-end
gameplay evidence pipeline still requires [#33](https://github.com/CVX-Hull/enactive/issues/33).

The evidence store uses format version 2 and exposes `source_status(reference)`
as `retained` or `disputed` after identity/integrity verification. Disputes persist
across newer observations and reopening, including after damaged bytes are restored.
Stale current authority alone does not dispute historical truth. Version 1 stores
are archived evidence, not current runtime inputs; create a fresh store for a new
task. Neither historical status grants current input permission.

`authority_generation()` is process-local invalidation history: it advances when
current identity changes, validation invalidates evidence, or the store closes.
Returning to an earlier frame cannot conceal an intervening rejection. It is not
an execution token and is not restored; a new store/memory starts without current
authority.

## Passive task memory

[TaskMemory](../harness/gameplay/memory.py) belongs to one immutable TaskSpec and
EvidenceStore. It retains source facts, explicitly non-factual interpretations
and hypotheses, candidate plans, versioned procedure/failure references and action
results as separate immutable views. It dispatches nothing, advertises no executable
skills and infers no task completion. The store alone retains original frames.

Explicit `refresh` can retain fresh facts; `snapshot` rechecks existing history
without promoting a new observation. Both and `retain_plan` require caller clocks;
snapshots describe that instant, not live authority. Source disputes invalidate
dependent records. Staleness, observation identity or store generation changes,
unknown/conflicting actions, task/session/epoch changes and capacity failures
invalidate candidates. Epoch advance preserves verified history. Task replacement
retires the instance; restart never restores memory or a lease from a journal.

Identical action IDs are idempotent; conflicts preserve the original and mark the
conflict. Recorded displacement must match referenced positions. Cross-session
after-evidence remains unknown context, never progress. Capacity is checked before
append: 128 facts, 32 interpretations, 32 hypotheses, 16 plans, 16 procedures,
32 actions, 64 KiB text including diagnostic reserves, 1024 chars per annotation
and eight source references. No silent eviction. Source-status scans deduplicate
up to the store's 32 frames; freshness/fact/position access may add targeted hash
reads. Retained-byte limits are storage limits, not total I/O measurements.

## Bounded injected planner

[`PlannerPort`](../harness/gameplay/planner.py) belongs to one immutable TaskSpec.
Construct it with `PlannerConfig`, a trusted provider callable and the original
`admission_monotonic` in seconds. This is the same admission origin used by
[evaluation](evaluation.md), with explicit seconds-to-milliseconds conversion.
Construction and delayed first submission do not restart the task clock. The first
invoked request pins the exact start EvidenceRef; continuation cannot replace it
or replenish the original turn/call/time/spend ceilings.

`PlanningRequest` supplies typed task/evidence, accepted skill descriptors, exact
plan/version/epoch, expected outbound/return stage, remaining distance and bounded
public context. The caller owns route progress and capability truth. The provider
receives immutable serialized `ProviderInput` and a cooperative cancellation event,
then returns `ProviderReply(candidate_json, usage)`. It receives no controller or
filesystem handles. Trusted Python injection is not an isolation sandbox.

`submit` reserves cost before invocation and returns a unique call ID. `poll` takes
that ID and the caller's current `PlanningBinding`; mismatches permanently discard
applicability. Candidate JSON must satisfy the existing PlanCandidate schema,
binding, supplied skill/version and exact route semantics. Success returns data,
never permission to dispatch. `cancel` and `close` invalidate pending/completed
candidates; close returns without waiting for a stuck provider. No automatic retry,
restoration or model selection occurs. The runtime supplies the external-chat
provider; deterministic fixtures remain test-only.

| Limit | Contract |
| --- | --- |
| Concurrent/lifetime calls | One physical call; at most ten lifetime calls per port |
| Context/reply | At most 1 MiB each; defaults 1 MiB / 16 KiB |
| Input/output tokens | Network/fixture declared bounds at most 1,048,576 each; defaults 32,768 / 2,048. External chat usage is unmeasured and not enforced by this adapter; bytes are not token estimates |
| Supplied capabilities/context | At most 32 descriptors and 4096 public-context characters |
| Uninvoked rejections | Last 64 audit entries plus total/dropped counters |
| Deadline | At most 30 seconds per call, further limited by task and remaining budgets |

A timed-out call retains the physical slot until its provider exits, preventing
thread accumulation. Deadline, cancellation, close and stale bindings win over late
results. Provider completion is recorded separately from the stop and financial
settlement timestamps. Unknown cost does not keep an already completed call's
measured duration running.

Network mode requires declared credential availability, bounded pricing and a
positive operator-approved spend ceiling/reservation. Missing prerequisites reject
before invocation. These are adapter declarations, not credential discovery or a
billing-system guarantee. External mode requires zero API reservation/spend; it
enforces byte/call/deadline/gameplay bounds but cannot measure or cap the surrounding
Codex chat usage. `external-unreported` explicitly marks unavailable model provenance;
`external-chat-v1` identifies the adapter configuration. Usage fields remain null,
not fabricated zero tokens or subscription cost. Missing cost
or malformed/contradictory usage retains the reservation; valid actual cost can
settle even when token metrics are absent. Over-bound raw usage freezes future
calls before evaluation sanitization. Representable overshoot remains visible;
unrepresentable overshoot is null with a reason. Failed and cancelled calls retain
late cost without reviving their candidate.

`snapshot(cutoff_monotonic=...)` returns immutable accounting and exactly one
`evaluation/1` event per invoked call. Uninvoked rejections stay separate. Record
one snapshot once, with other events in timestamp order. Later knowledge belongs
in a new named artifact; do not append repeated snapshots as duplicate model calls.
Unknown metrics carry reasons. A physically unfinished call is censored at cutoff;
a completed call ends at physical completion even if its reservation is unsettled.

## Passive bounded movement skills

`harness/gameplay/skills.py` implements `MovementStage` and the versioned
`CARDINAL_MOVEMENT` descriptor. `ACCEPTED_SKILLS` contains this one capability.
Descriptors declare implemented predicates; arbitrary strings are not executable
conditions. Cardinal skill version 3 supports the remaining part of outbound/return
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
play, unpaused/unfrozen control, known absence of visible creatures and valid current
position. A registered cardinal action is required even at completion. At an exact,
fully credited target this current-boundary check suffices; before any further step,
the full `guard` additionally requires a CLEAR empty allowlisted cardinal neighbor.
Evidence still requires all eight cells: an invisible future neighbor may omit its
hidden contents, but a missing cell is invalid. Public controller `walk` retains its
conservative next-neighbor check after every step. Version-2 cardinal candidates
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

The passive supervisor below owns task completion, handoff, epochs and nonprogress
readmission. The runtime above connects this passive caller to controller leases. The [native acceptance](acceptance/2026-10-17-bounded-skills.md)
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
[reviewed design](changes/010-passive-supervisor.md) for ownership, migration and
acceptance. The runtime adds production integration without making this package
a dispatcher. Planning revalidation and non-authorizing status inspection support
slow external decisions while preserving fresh-input guards.

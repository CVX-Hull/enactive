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
and the host token are separate authorities; future run leases will use this same
revocation mechanism.

The SDL input loop pumps normal events while polling. RAII scopes span
`input_context::handle_input`, including retries and nested contexts. An explicit
marker at ordinary avatar input distinguishes normal play; deathcam, unknown
DEFAULTMODE callers, activity polling and raw debug prompts cannot inherit it.
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
Immediate interruption from an unpaused activity can reject when the native Pause
revision invalidates its prior capture. The current operator workflow is explicit
Pause → Observe → decide whether interruption is still eligible; no automatic
refresh or retry. Broader timing acceptance remains #8.

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
claims. JSON is bounded to 1 MiB. These are interfaces, not a running planner,
supervisor, model adapter or task executor. The [larger design](design/gameplay.md)
remains the specification for those later consumers.

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
retained peers. Historical references remain verifiable but cannot authorize input.
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
gameplay evidence pipeline still requires [#33](https://github.com/CVX-Hull/cdda-player/issues/33).

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

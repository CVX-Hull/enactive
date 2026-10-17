---
owner: maintainer
review_trigger: Native bridge, controller, input, observation or skill change
status: active
---

# Bridge and guarded-play contract

Protocol version: 2.

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
directory. Version 2 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. One request is outstanding at a time; the host holds a
process lock. Requests carry protocol, unique id, session, expected revision,
kind and payload. Size is bounded to 4096 bytes. World entry and exit replace the
session, including a same-process save/reload; relative coordinates belong to that
world lifetime. Stale session/revision commands are rejected, never replayed.
Producer, controller, discovery and CLI must agree on v2; there is no v1 fallback.

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
nonnegative `control_generation`, `recovery_operations` (currently empty), and
`interrupt_request_id` (currently null). Boundary instances change with context,
session and native takeover, rather than every repaint. The supported matrix is:

| Kind | Observe | key/action/resume | Structured scene |
| --- | --- | --- | --- |
| `normal_play` | Yes | Fresh matching frame and authority required | Player-visible allowlist |
| `menu` | Yes | Fresh matching frame and authority required | None |
| `activity_poll`, `debug_prompt`, `unsupported` | Yes at instrumented polls | Rejected | None |
| `interrupt_confirmation` | Reserved for future owned recovery prompts | Rejected | None |

Menu classification is explicit in the native scope constructor; unrecognized
categories remain unsupported. A registered action is not permission to act at an
unsupported boundary. Recovery requests/confirmation/debug dismissal are not yet
implemented; native keyboard input remains the recovery path.

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

[EvidenceStore](../harness/gameplay/evidence.py) accepts only native-v2 positively
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

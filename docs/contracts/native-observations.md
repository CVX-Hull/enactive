---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Native commands, visible observations and boundaries

The game enables the bridge only when CDDA_HARNESS_DIR names an existing private
directory. Version 6 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. Each channel admits one live request at a time; the host holds a
process lock for both writers. Gameplay and recovery retain separate identities. Requests carry protocol, unique id, session, expected revision, intended boundary,
human takeover generation,
kind and payload. Size is bounded to 4096 bytes. World entry and exit replace the
session, including a same-process save/reload; relative coordinates belong to that
world lifetime. Stale session/revision commands are rejected, never replayed.
Producer, controller, discovery, CLI, viewer and evidence validation require v6.
Older and unknown versions are rejected; there is no fallback.

Commands: observe, key, action, direct, pause, resume. Observe is side-effect-free in
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

Every observation has required`frame_geometry`: null when`frame_ok=false`,
otherwise positive window/output width and height (maximum16384 each) and a
four-integer viewport`[x,y,width,height]` within the full output. Width/height
must be positive and total output at most16777216 pixels. Native capture retains
the full default render output in a matching allocation. Direct click geometry
must equal that retained geometry and the final current geometry; its PNG pixel
maps separately to engine window coordinates and widget output coordinates.
The harness uses an internal synthetic pointer, never moves the Mac pointer or
requests focus, and consumes balanced widget press/release through bounded normal
render frames. Postcommit consumption failure is dispatched/unknown with fault
Pause, never a known zero-input rejection or a later success acknowledgment.

The SDL input loop pumps normal events while polling. Context RAII scopes span
`input_context::handle_input`; receiver RAII spans the existing game-thread
`input_manager::get_input_event()` render/poll path. Required boolean
`boundary.input_receiver` attests that the live receiver matches the actual top
context and depth. A raw receive without an active context cannot attest ordinary
eligibility. Receiver entry/exit alone does not mint a revision or boundary ID.

Ordinary contexts may have unfamiliar category/action names; no menu-name catalogue
grants permission. Explicit avatar scope anchors normal play; deathcam/unsupported
owner, debug, activity and owned interrupt restrictions take precedence through
nested contexts. Inherited restriction does not confer inherited recovery power:
activity interruption and its owned query remain tied to their actual owner/depth.
Incidental animation polls are unscoped. The explicit lifecycle flag around
main.cpp's do_turn loop gates gameplay metadata, not character identity. Visible
death still ends an admitted survival study. Semantic adapters retain their narrow
registered-category/control coverage; ordinary receiver support does not qualify
a structured health model, recipe, consumption or other effect. Historical
[direction](../acceptance/2026-10-18-native-direction-menu.md),
[distraction](../acceptance/2026-10-18-activity-distraction.md) and
[native5 discovery](../acceptance/2026-10-21-discovery-learning-fourth-attempt.md)
results retain their tested binary and scenario scopes.

Each observation's required `boundary` has `kind`, nonempty `id`, nonnegative
`control_generation`, boolean `input_receiver`, zero or one `recovery_operations`
and `interrupt_request_id` (nonnull only for owned interruption confirmation).
Boundary instances change with context, session and takeover, rather than repaint
or receiver timeout retries. Remote key/text/click translation feeds the existing
engine/widget path without OS input; physical takeover retains precedence.

| Kind | Observe | Ordinary input | Structured scene |
| --- | --- | --- | --- |
| `normal_play` | Yes | Live receiver, fresh dispatch evidence and authority; semantic policy also applies | Player-visible allowlist |
| `menu` | Yes | Live receiver, fresh dispatch evidence and authority; semantic policy also applies | None |
| `activity_poll`, `debug_prompt`, `unsupported` | Yes at instrumented polls | Rejected | None |
| `interrupt_confirmation` | Yes at the owned rendered question | Rejected | None |

Observe and an advertised action alone grant no permission. Recovery uses its
separate [exact-owner recovery channel](operator-recovery.md); nested help cannot borrow it. Native keyboard
input remains available.

At an eligible rendered boundary the bridge publishes observation metadata and
PNG. Publication redraws the current UI and captures the window backbuffer
immediately before SDL_RenderPresent, checking boundary/session/revision provenance;
the older display-buffer screenshot helper omitted ImGui popup content.
PNG names are immutable session/frame-counter identities, with metadata
published after the corresponding atomic file rename. The viewer grants input
authority only after that image decodes and matches the latest session/revision;
old asynchronous decodes cannot restore a fresh label or authorize an old choice.
Every ordinary action/key/direct/resume wire envelope requires the actual generated
`frame` and a strict boolean `require_exact_frame`; prior field sets reject.
When true, host preflight verifies the retained encoded PNG hash and native commit
encodes the latest cached presented surface through the existing PNG encoder,
compares bounded bytes exactly, then rechecks authority/deadline/boundary/Pause.
Direct must use false, allowing changed pixels while retaining actual saved-frame
provenance, receiver/custody and click-geometry checks. Semantic/lifecycle policies
retain their stronger requirements; false alone is never input authority.
This source path assumes the one trusted bridge writer owns the comparison
temporary file; it does not claim exclusion of arbitrary same-user filesystem
mutation or physical events queued during synchronous encoding. Real encoder
repeatability, changed-image rejection and latency require native qualification.
A command is dispatched at
most once within the live session; the next input boundary acknowledges that
the engine has returned to input, not that the intended gameplay objective
succeeded. Prompts and menus are valid outcomes and require new interpretation.
Unrecognized keys may leave the category unchanged. Long activities may not
yield promptly: host deadlines produce **unknown outcome**, freeze further
actions, and require observe/reconciliation. No automatic action retry.

## Native request lifecycle and unknown outcomes

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

[Contract index](../protocol.md).

# Architecture and initial decisions

Owner: lead. Updated: 2026-10-17. Status: implemented MVP contract; verification
scope and limitations are in [work.md](work.md). Protocol version: 1.

## Outcome and non-negotiable boundaries

Codex plays the real CDDA engine. The user sees the native Tiles renderer in a
normal window plus a local spectator console showing current frame, goal,
actions, and control state. All new tooling, game data, saves and logs stay
project-local or in a recorded temporary build directory. Native keyboard
takeover and a prominent pause control remain available. The model never reads
save files or undiscovered map state to improve normal play.

The MVP supports one game and one controller. Current Codex is the high-level
planner, using the harness CLI; no paid API key or independently running LLM
service is required. General autonomous survival, VLA training, multiplayer,
cloud hosting, and arbitrary game versions are outside the first release.

## Platform decision

| Candidate | Benefits for this goal | Costs / evidence limits | Decision |
| --- | --- | --- | --- |
| Native arm64 SDL Tiles with a source bridge | Original renderer, direct window, lowest component count, controllable input boundary | Local compilation; source patch must be maintained | MVP |
| Linux container + Xvfb + noVNC | Clean-room runtime, parallel headless sessions, browser streaming | VM/display/transport layers; startup and input integration; no measured advantage for this single-user run | Revisit for unattended or multi-instance evaluation |
| Upstream Emscripten | Browser-native viewing, upstream build support exists | Asyncify, persistence and browser execution add integration work; not benchmarked here | Revisit if browser delivery becomes primary |
| Screen-only native automation | No source patch | OCR/context ambiguity, high interaction cost, weak action acknowledgment | Fallback/manual diagnostic, not primary transport |

This is a requirements decision, not a claim that native is universally faster.
Pinned upstream 0.I-1 includes native and Emscripten build support. We choose
native because the user wants a visible local game and reliable closed-loop
control. We can move the file protocol and controller to Linux later without
designing a general deployment system now.

## Components and authority

1. **Game patch**: opt-in local bridge in input_context and SDL input handling.
   Only the game thread reads/writes game state. It exports an actual framebuffer
   and current input category/actions. Minimal world observations, if included,
   are gated by the same visibility rules as the UI and only in normal play.
2. **Controller service/CLI**: sole serialized file-protocol client. It validates
   requests, journals decisions/results, serves the viewer on loopback, and runs
   bounded skills. It cannot directly mutate game state or saves.
3. **Viewer**: actual game frames with explicit age and status; never a fake game
   rendering. Pause/resume and action explanations. Browser pages cannot issue
   commands without local origin/token validation.
4. **Planner**: Codex reads observations, selects objectives and verifies results.
   It may request a bounded skill but cannot infer success from a key sent.

## Bridge contract

The game enables the bridge only when CDDA_HARNESS_DIR names an existing private
directory. Version 1 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. One request is outstanding at a time; the host holds a
process lock. Requests carry protocol, unique id, session, expected revision,
kind and payload. Size is bounded. A restarted game creates a new session;
stale session/revision commands are rejected, never replayed.

Commands: observe, key, action, pause, resume. Observe is side-effect-free in
gameplay terms. Key is one ASCII character or named navigation key, never an
unbounded string/macro. Action chooses a binding registered in the active input
context. Pause prevents further remote inputs; resume is explicit. Native human
keyboard/button input latches takeover and increments revision. Mouse motion
alone does not pause. A separate pause sentinel may interrupt a pending host
routine even while the serialized command is waiting; it cannot reverse an
already dispatched engine action.

The SDL input loop pumps normal events while polling. Eligible boundaries are
scoped immediately around each input_context::handle_input call to
get_input_event, including invalid-key retries. Incidental animation polls are
unscoped and cannot dispatch or acknowledge commands. Capture follows the
existing SDL refresh. An explicit lifecycle flag around main.cpp's do_turn loop
gates gameplay metadata; DEFAULTMODE alone is insufficient because the main
menu reuses it for keybinding settings. Remote input_event delivery includes an
SDL/ImGui adapter for key/text events without sending OS events; native events
are separately observed for takeover.

At an eligible rendered boundary the bridge publishes observation metadata and
PNG. Capture copies the window backbuffer immediately before SDL_RenderPresent;
the older display-buffer screenshot helper omitted ImGui popup content.
PNG names are immutable session/process/counter identities, with metadata
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
absolute expiry. On startup or timeout the controller writes the pause sentinel
first, then attempts an atomic rename of an undispatched request to a retired
file. If the game won the claim race, disposition is unknown until a matching
terminal response or expiry plus paused observation establishes reconciliation.
Never overwrite/retry an unresolved gameplay request. A new observe may restore
knowledge of current state but cannot prove the original objective succeeded.

All outcomes include request id, session, revision, category, pause state,
timestamp, frame reference and error/status. Revision tracks accepted remote
inputs and meaningful native input. Observations include age; a missing/stale
frame is visible. The bridge must not falsely acknowledge successful capture.
Frame metadata is published only after its PNG is atomically replaced. World
turn changes and context/action-set changes invalidate revisions too. TURN_DURATION
is fixed at zero for the MVP. Resume increments revision, requiring new command
authority. Planner commands carry the session/revision from the observation
used to choose them; fresh-observing cannot silently authorize a stale choice.

## Efficient closed-loop play

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

## Failures and recovery

Game crash: report disconnected and preserve last evidence. Service restart:
read journal and current session; never replay pending action. File corruption:
reject bounded request and surface diagnostic, continue native game. Pause:
stop before the next dispatch and permit human control. It does not cancel an
already-started native activity; the native window remains the interrupt path.
Raw upstream debug/error screens outside input_context are unsupported and may
require native dismissal while the service stays frozen. Game restart: old
requests fail session validation. Observer access is loopback only, no remote
exposure. Shutdown closes the service and leaves saves managed by CDDA's normal
save UI; no destructive process cleanup or automatic save editing.

## Acceptance probes

Compile the pinned patch; launch windowed with explicit project userdir; inspect
real frames. Exercise main menu, character creation, normal play, inventory,
confirmation prompt, movement, item use, pause, native takeover, stale input,
save/reload and disconnect. Use a visible danger scenario without debug state.
Record a continuous meaningful session with actual before/after observations.
Unit tests cover transport and control invariants, not game simulation. Exact
test results and limitations live in work.md.

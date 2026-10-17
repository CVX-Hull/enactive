# Architecture and initial decisions

Owner: lead. Updated: 2026-10-17. Status: implementation contract, not a claim of
working software. Protocol version: 1.

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

The SDL input loop pumps normal events while polling. At a rendered input
boundary it publishes observation metadata and PNG. A command is dispatched at
most once within the live session; the next input boundary acknowledges that
the engine has returned to input, not that the intended gameplay objective
succeeded. Prompts and menus are valid outcomes and require new interpretation.
Unrecognized keys may leave the category unchanged. Long activities may not
yield promptly: host deadlines produce **unknown outcome**, freeze further
actions, and require observe/reconciliation. No automatic action retry.

All outcomes include request id, session, revision, category, pause state,
timestamp, frame reference and error/status. Revision tracks accepted remote
inputs and meaningful native input. Observations include age; a missing/stale
frame is visible. The bridge must not falsely acknowledge successful capture.
Frame metadata is published only after its PNG is atomically replaced.

## Efficient closed-loop play

Use goal → bounded skill → one primitive → fresh observation → verification.
Start with movement, menu navigation and single actions. Movement routines have
a small step limit, require normal-game context, and stop on a prompt, no
progress, visible threat, damage when observable, pause, stale revision or
transport error. Unknown information stops a routine instead of assuming safe.
Maintain observed facts with provenance/age; do not infer an unseen route is
clear. The model chooses high-level objectives, while deterministic guards
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
stop before the next dispatch and permit human control. Game restart: old
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

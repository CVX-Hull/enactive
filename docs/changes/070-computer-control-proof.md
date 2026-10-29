---
owner: lead
review_trigger: Candidate mechanical protocol, backend or delivery scope changes
status: proposed
---

# Basic computer-control proof (#181)

Owner-selected boundary: [ADR006](../decisions/006-computer-control-boundary.md).
This is one isolated enabler, not production #176/#284 or a compatibility backend.
The candidate and all support live in `experiments/computer_control/`; the product
CLI, native7/mission11 and their historical evidence are unchanged.

## Backend decision and user consequence

Compare Apple OS/window capture/event posting with a reduced SDL bridge. A local
nonprompting CoreGraphics preflight reports capture available but event posting
unavailable. No permission request/settings change was made. Existing OS capture
is viable, but input would need user permission plus foreground/coordinate and
human-input discrimination work. No maintained OS-control dependency is installed
in this project. Retain this as a deployment-specific limitation, not an Apple
capability failure.

Selected candidate: a small SDL2 event/render shim loaded only into the exact
owned child via Apple's dyld interposing interface. Use the installed SDL2 and
SDL2_image frameworks and Foundation JSON; no global installation or engine
rebuild. The prepared game stays authentic: the old semantic bridge environment
is absent, and no game state, input context, widget or save is read/edited by the
shim. Its only integration calls are SDL event/window/renderer and file IPC.
The experiment derives the maintained prepared wrapper, replacing exactly its
old-bridge export with `unset CDDA_HARNESS_DIR`; resource paths, project userdir,
windowed configuration and background hints remain. Freeze that wrapper and the
effective child environment (without provider credentials). This reduces
engine-source coupling without claiming cross-game portability.
Interposition availability/signing, key/text semantics and pointer state are
feasibility questions to test, not assumed support.

The player receives actual frame pixels and basic key/text/pointer/bounded-wait
controls. It chooses all game interpretation, goals, recovery and ending. No
menu/scene/row/identity/activity/turn/goal fields or predicates exist in candidate
input authority. Optional player-level action sequences contain only those basic
operations and cannot renew original limits. Bad choices/loops remain behavior.

## Mechanical contract and ownership

One fresh0700 run directory, exclusive writer and exact subprocess handle. No
process adoption, native7 inbox, old lease or automatic rearm. One SDL window is
bound on its first renderer; destruction/loss stops new dispatch, never retargets.
The native session is the fresh launch ID. State is `computer-target/1`: session,
pid, window ID, paused/takeover generation, mechanical capture/geometry and error.
Captured PNGs come only from full default-target renderer pixels before present;
no structured game metadata. A snapshot reports capture/presentation times without
promising current meaning or success.

`computer-request/1` uses a unique32hex ID, exact session, bounded expiry and
`kind=observe|input`. Input is one key/modifiers, <=31UTF8-byte text event or click
with original full-capture geometry. Every physical event passes the application's
normal SDL handling. Keys/text have no image-equivalence prerequisite. Pointer
output coordinates map to the matching window geometry; changed mapping refuses
before input, with no silent rescale to another capture. Non-default logical-size
transforms remain unsupported until actually tested.
The first real episode exposed a polling-time offscreen texture: SDL's current
renderer queries then describe the texture, so they cannot validate window clicks.
Capture remains default-target-only. Pointer dispatch compares the complete last
presented geometry plus independent window-size/pixel-size witnesses; when the
default target is selected it also checks current default geometry. It never
switches the application's render target. A smaller offscreen fixture reproduces
that boundary, preserving stale-click refusal after resize and no retarget after
renderer destruction. This is a mechanical SDL distinction, not a game handler.

`computer-receipt/1` records the exact ID/session, delivered/rejected/partial/unknown,
emitted event count, reason and optional captured frame. Delivered means SDL events
were handed to the application, never proof it processed or acted successfully.
Do not replay a timeout or partial input. Immutable exact-ID receipts permit only
collection. Native JSON/file faults after any emitted event cannot become a
zero-input rejection. Input key/button release is mechanical cleanup, not another
game command. Pause/takeover cancels further command events, permits only required
neutralization and never automatically resumes.

Real SDL events always precede synthetic stages: call the real PollEvent first
and emit only after it reports an empty queue. No bounded drain may assume an
unresolved queue empty. Each subsequent stage rechecks Pause/takeover. Physical
key down/up, text/IME editing, button/wheel, joystick/controller/touch input
latches takeover and preserves the human event. Unpressed pointer motion yields
virtual pointer state to the real pointer without pausing; motion with buttons
held is takeover. Window lifecycle events remain mechanical, not game categories.

Emit at most one synthetic event per PollEvent drain, followed by an explicit
empty result before the next stage. This permits the application to process a
press before release. Scoped SDL_GetMouseState/GetGlobalMouseState and modifier
queries supply only owned virtual device state; no ImGui/widget calls or global
SDL_SetModState mutation. On takeover return real state without clearing human
buttons/modifiers. Test classic SDL input and actual game/widget paths separately.

Cancellation after publication first latches persistent Pause, then abandons the
await; native checks that fence before every command event. An outstanding
request may have partial/unknown delivery; allow only collection and required
neutralization afterward. EOF/signals also latch Pause before the MCP process
settles. External Pause is a persistent file. One original
monotonic run deadline and finite input/request/frame/byte limits belong to the
custodian/writer. Native per-request expiry and bounded event drain complement,
not replace, that anchor. Lost ACK/target/storage stops input with uncertainty;
process shutdown is distinct from normal exit and player-claimed Save/success.

## Implementation and checks

- Native `bridge.mm`: SDL render/event interposition, target binding, capture,
  raw event conversion, state and immutable receipts; no CDDA headers/types.
- Native `fixture.cpp`: independently shaped SDL window using raw controls, for
  actual adapter input/geometry/takeover/capture and shutdown assertions.
- Python protocol/client/MCP: existing MCP library, canonical files/correlation,
  original limits, <=32-basic-operation sequences, result collection, PNG replies.
- Python build/run entry: project-local dylib/fixture builds, frozen data, exact
  owned child, one generic Pi host with existing OpenRouter Fireworks US route,
  read-only spectator plus operator Pause, diagnostic events and cleanup receipts.
  Reuse existing Pi/host analysis; no new planner, database, framework or provider.

Fast/focused committed checkpoint before gameplay; independent boundary review
before the affected commitment. Test malformed/duplicate/session/expiry, target
loss, unknown/no-replay, partial neutralization, Pause and cancellation, changed
geometry and unchanged frames. Separate native fixture/build evidence from portable
fixtures. Then early meaningful organic play: player chooses a useful survival or
scouting goal and acts from pixels; retain failed/censored/abandoned goals and all
setup/decision/repair/ending costs. No lead gameplay inputs or manufactured bad
routine. The exact finite package is selected prospectively after this checkpoint.

## Scope, stop and completion

#181 is8–12active hours/Low, with a4hfeasibility checkpoint and12happetite.
A tested no-go can close only its backend/contract decision, not basic-control or
full-product acceptance. Stop at a concrete ownership/capture/input/permission
blocker; do not transplant a semantic veto or bypass authentic engine input.

Positive completion includes native raw operation evidence, a source-linked useful
goal attempt independently assessed, and an implementable reviewed deletion/caller
map for #176: native/controller, admission/ledger/evidence, tools/programs/context/
memory, driver/custodian, spectator, tests/docs and unsupported-format rejection.
Retain actual resize/non-unit pointer/old-click/takeover/Unicode gaps explicitly.
No claim of20useful decisions, useful cadence, seven-day survival or second real
game unless its original evidence exists. One coherent PR, independent review,
appropriate full protected PR/main checks, current docs/tracker and owned cleanup
precede Done. Historical paused3177329 source is preserved for reuse/retirement.

## Reuse references checked October29,2026

[Apple's event-posting preflight](https://developer.apple.com/documentation/coregraphics/cgpreflightposteventaccess%28%29),
[window capture](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos),
[dyld interposition header/example](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld-interposing.h),
[SDL2 event polling](https://wiki.libsdl.org/SDL2/SDL_PollEvent),
[renderer capture](https://wiki.libsdl.org/SDL2/SDL_RenderReadPixels) and
[event posting/device-state distinction](https://wiki.libsdl.org/SDL2/SDL_PushEvent).
The installed SDL2.30.11 [renderer implementation](https://github.com/libsdl-org/SDL/blob/release-2.30.11/src/render/SDL_render.c)
and [window pixel-size API](https://wiki.libsdl.org/SDL2/SDL_GetWindowSizeInPixels)
explain the offscreen/default geometry distinction found during actual play.
These API contracts do not attest the current target's signing, actual permission
availability, input parity or useful gameplay; native probes own those claims.

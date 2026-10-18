---
owner: lead
review_trigger: Native direction classification, keybindings, campaign recovery or build changes
status: proposed
---

# Support the engine's explicit direction chooser

[#91](https://github.com/CVX-Hull/enactive/issues/91) blocks autonomous first-day
work. The [failed rehearsal](../acceptance/2026-10-18-first-day-rehearsal.md)
required user Escape at an ordinary adjacent-pickup query. The reuse-first
[native-window plan](016-autonomous-native-recovery.md) could not reach admission:
the UI tool reported a lock/access failure before binding or launching a game.
No user unlock was requested, no character loaded and no probe input charged.
Its passive Observe timed out with no native process; retain that diagnostic.
Do not make desktop UI availability a prerequisite for this normal engine query.

## Design and reuse

Reuse CDDA's common `choose_direction` implementation, registered directions,
cancel/selection semantics, keybinding lookup and real renderer. Preserve its
original DEFAULTMODE binding category. An independent review found that renaming
it would lose the current-tile `pause` binding and DEFAULTMODE-local overrides:
the engine's fallback is `default`, not DEFAULTMODE. Reject that initial design.

Add a small game-thread RAII `direction_query` marker **only around this helper's
actual `ctxt.handle_input()` call**, ending before its callbacks/outcome handling.
It activates only during the game lifecycle with an empty input-scope stack and
no already active direction query. The native input-scope constructor admits
DEFAULTMODE as `menu` only when this marker is active and the scope stack is still
empty. Keep the published category DEFAULTMODE and actual binding lookup unchanged;
menu has no structured gameplay scene. Any nested context, debug/activity scope,
unmarked DEFAULTMODE or callback after the query remains under existing policy.
RAII unwinding clears only the marker owned by that invocation. The actual engine
still validates the direction/selected tile and decides whether to open inventory,
cancel or do nothing.

This covers the existing chooser used by pickup and other genuine direction
questions; it does not classify arbitrary translated messages or hand-code every
possible outcome. Do not promote DEFAULTMODE globally or give menu observations
normal-play authority. Existing debug/interrupt precedence, input token, Pause,
fresh frame/session/revision and unknown handling stay intact. Unrecognized
contexts remain unsupported; absence of a fact never becomes permission.

Pin `src/action.cpp` by its bytes from the already checksum-verified official
0.I-1 source archive. Add the exact-once call wrapper through the existing patcher
and preserve its repeatability/hash/ambiguous-anchor rejection. No context rename,
copied keymap, binding inheritance layer or compatibility reader. Verify actual
Escape, adjacent-direction and current-tile `pause` selection after building.

Owned implementation: `native/upstream.json`, `native/cdda_harness.h`,
`native/cdda_harness.cpp`,
`tools/patch_game.py`, `tests/test_setup.py` and a focused controller contract test
if existing coverage lacks the explicit menu case. Current contract/operations
guidance and dated evidence move with the change. The independently isolated
#79 objective view uses only `web/index.html`, `web/app.js`, `web/style.css` and
`tests/test_viewer.cjs`; integrate/review it before committing the candidate, never
change source during native acceptance. One lead integrates and owns runtime.

## Validation and delivery

1. Independently review this design and binding/classification evidence. Run
   patch repeatability, pinned-hash and duplicate-anchor negative checks; verify
   the controller accepts a current menu and rejects unsupported/stale/paused
   authority. Fake transport tests cannot prove native classification.
2. Commit the exact reviewed candidate with the public identity and mandatory
   common checks. Build the pinned native source using the existing project
   recipe/owned temporary workspace; preserve the old manifest/binary and record
   the new build/install hashes. No new compiler flags, dependency or global setup.
   Exact-candidate CI and actual build must pass before installation/acceptance.
3. Stop affected processes before installing the matching native build. Launch
   one prepared windowed bundle with its explicit project userdir. Use native
   frames through the bridge/spectator; no OS unlock, synthetic desktop event or
   user keystroke is required. If actual frames/control are unavailable, stop
   with evidence rather than asking for routine rescue.
4. Admit one **30-input, ten-minute** restart/direction probe after exact source,
   binary, process/port and current-frame checks. Stop investigative input at
   24 inputs/nine minutes; reserve six/final minute for normal cleanup. All load
   menus, reasoning, Pause, unknown/rejected requests and cleanup count. No movement,
   consumption or rest objective; at most 60 game seconds beyond pre-save state,
   including native-owned overshoot. This is not a renewed survival allowance.
5. Load the normally saved Sneedville/Ramiro Winston through actual UI, retaining
   lifecycle unknowns and using the existing15-second loading timeout. Reconcile
   only after expiry. Apply brief015's bounded name-inspection admission if needed;
   compare current rendered name/calendar/needs/inventory with day61 08:00:32,
   six ration boxes, two frozen clean-water portions and active phone54/56. Old
   coordinates/leases are invalid. Conflict, ambiguity or regression stops.
6. From fresh supported evidence and explicit Resume, open adjacent pickup once.
   Require the actual rendered direction question, DEFAULTMODE/`menu`, a current PNG, no scene and
   no pending/lease. Exercise Pause refusal without dispatch, fresh Observe and
   explicit Resume; then Escape through the validated controller and inspect the
   cancellation. Reopen from new evidence, select one visibly valid direction,
   inspect actual inventory names and cancel without taking supplies. Also exercise
   registered `pause`/current-tile selection from the direction query. An empty
   current tile may close the query without opening inventory; record that limit
   rather than claiming successful current-tile pickup. Optionally
   inspect the existing pickup_all alternative; no outcome is inferred from a
   delivered key alone. Unexpected unsupported/unknown state stops the probe.
7. Inspect the objective near the native view at ordinary browser size if that
   cohesive view is included. It must remain a recorded objective, not invented
   progress or an active survival supervisor. Native frames and portable UI tests
   are distinct evidence. Normal Save and quit, current main-menu inspection and
   normal Quit finish cleanup; preserve lifecycle unknowns and verify process exit.
8. Independently review native/semantic claims and all original charges. Publish
   evidence and exact merged-main CI before closing #91. #79/#80 retain their
   broader UI, first-day and continuity acceptance; #81/#82 remain gated.

Retain pilot001's18inputs/229.232seconds, rehearsal001's57/727.918 and the separate
five-input menu operation, plus the unadmitted UI-access failure with zero probe
inputs. Aggregate/semantic limits remain lead-enforced, not a controller-wide
ledger guarantee. One proposed probe only; another requires a prospective replan.
The deciding seven-day campaign still needs its own fresh admission and no user
intervention. A successful development probe is not seven-day or learning efficacy.

## Migration, maintenance and limits

Wirev3 fields/types and persisted formats do not change: category is an existing
opaque string and menu is an existing kind. All existing consumers handle the
current category; no alias, old category reader or version negotiation is added.
Deploy the new native build with this source, restart to new authority and retain
old requests/frames as immutable history. Never relabel the old unsupported
pickup frame or replay an unresolved input. No save conversion/edit/deletion.
Rollback would restore a coherent reviewed source/native set after normal shutdown,
with all saves/unknown evidence preserved, not enable a mixed-component fallback.

The lead owns the patch, pin, build and native validation; read-only reviews can
parallel isolated objective implementation. Reassess at an upstream pin/chooser
change or another unsupported ordinary query; #75 retains broader maintenance.
This narrow menu support does not promise all native menus, combat, hidden-state
identity or general recovery. Retain native coverage gaps explicitly.

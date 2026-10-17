# Work and acceptance

Owner: lead. Updated: 2026-10-17. MVP implemented and demonstrated on this Mac.
Acceptance below distinguishes real gameplay, protocol tests, and limitations.

| Slice | State | Exit evidence |
| --- | --- | --- |
| Research and environment comparison | Verified | research.md primary-source matrix; native/Linux/browser alternatives |
| Isolation and version control | Verified | Local Git checkpoints and hook; pinned local build; environment.md ledger |
| Contracts and maintained practices | Verified | Common checks, local hook, CI definition, independent source reviews |
| Native bridge | Verified for MVP | Fresh pinned-source build; actual frames, menu/text/input/scene probes |
| Controller and spectator | Verified for MVP | 44 Python tests; four viewer race scenarios; actual browser inspection |
| Guarded skills and demonstration | Verified | Real movement, supplies/use, danger, save/reload, comparison below |
| Handover | Verified | Saved survivor; viewer open; remote input paused; remaining limits explicit |

## Real-game acceptance, 2026-10-17

Platform: macOS 26.6.2 arm64, Xcode Apple Clang 21. Official CDDA 0.I-1 source
and universal app, locally built arm64 Tiles executable. Window 960×672 including
title bar; framebuffer 960×640. UltimateCataclysm tiles; FULLSCREEN=no;
TURN_DURATION=0; explicit project user directory. No debug-spawned character,
items or monsters, and no save editing. Ordinary Evacuee/Survivor defaults.
Survivor: Andres Lang, world H.

| Probe | Observed result |
| --- | --- |
| Fresh isolated build | `tools/setup.py --download --extract --build --jobs 6` passed with local FreeType headers, official bundled SDL/FreeType runtime; installed and launched |
| Menus and text | Main menu, world creation, case-sensitive YES/NO, character creation, inventory, item-use submenu, overmap; entered world name H and map note Base camp, including named SPACE |
| Renderer | Actual presented SDL frame, including ImGui popups; native and browser screenshots inspected; no fullscreen |
| Supplies and use | Activated smartphone flashlight; picked up emergency blanket/jacket, clean water and two rations; drank water; UI showed Hydrated and “You drink your clean water.” |
| Movement/exploration | Relative displacement checked; explored shelter aisles/stair room, opened doors, exited onto pavement, reached adjacent road, explored forest toward settlement |
| Guard interrupts | Refused near friendly NPC; stopped at wall/furniture; stopped when creature appeared mid-walk; refused at zero steps with hostile zombie visible |
| Native takeover | Native Escape closed inventory and latched pause at revision 73; remote movement rejected until explicit resume |
| Stale authority | Revision 71 command rejected after resume at 74; no displacement; old-session authority cannot survive restart |
| Persistence | Normal save/quit then new executable process; loaded at identical turn 5212875 with hydration and supplies. Second save/reload preserved forest state at turn 5213053 |
| Danger | Native travel displayed “zombie spotted! Cancel auto move?”; reconciled timeout, chose YES via harness, log confirmed auto move cancelled; visible zombie hostile=true; guarded walk refused |
| Failure recovery | Upstream vehicle error blocked an observation; timeout froze remote actions with no retry; native dismissal, explicit observe/resume, cancellation and save/reload succeeded |

Evidence stays local and ignored: `.runtime/sessions/20261017-150952-cf4e58a5/events.jsonl`
records creation and supplies; `.runtime/sessions/20261017-152033-c13a3850/events.jsonl`
records takeover, movement, persistence and danger. Game sessions were
`1792264486576-95555` and `1792265273783-10706`. Relative position resets at
new play entry; compare scene/time/UI, not relative coordinates across reload.
`.runtime/evidence/manifest.json` records hashes of curated artifacts and current
build provenance. Video is actual frames at 8×, not a simulation; its roughly
10-minute capture interval ends before the zombie encounter.

## Efficiency probe

Same clear shelter aisle, same direction, same three tiles: relative (2,7,0)
to (2,4,0), no visible creatures. Single actions returned revisions 90/92/94;
guarded north walk returned 102/104/106 after resetting along the aisle.
Both verified 3/3 displacements with no harness failure. Baseline used three
planner/tool decisions; routine used one, retaining a fresh native observation
and guard per step. Native dispatch-to-ready times summed to 152 ms versus
148 ms; the whole routine's CLI command took about 0.31 seconds. This tiny
single trial demonstrates fewer planner round trips, not statistical speed,
safety, or survival superiority. Human/model deliberation time was not measured.

The movement routine conservatively rechecks the next tile after its final
step. It may report stopped with all requested steps completed when the next
tile is a wall. `steps` is the observed displacement count; stopped is not proof
that no movement happened. Preserve that distinction when reporting outcomes.

## Verification and review

`python tools/check.py` runs Python/JS syntax, all 44 Python tests (including
loopback HTTP), four production-JS delayed-decode scenarios, required documents,
local links, and Git whitespace. It is also the repository-local pre-commit
hook. The GitHub Actions definition runs the portable lane; no remote CI run is
claimed because no remote was created. Native compilation and the real probes
above are separate acceptance lanes. Restricted sandbox HTTP binds initially
failed with EPERM; full checks were rerun with loopback permission, not skipped.

Independent contract, native and controller reviews found and drove fixes for
animation input boundaries, ImGui window IDs, failure cleanup, shifted keys,
queued pause/resume, stale viewer authority, delayed-image freshness, and named
SPACE. Lead inspected fixes, ran tests/builds, and performed actual gameplay.
The screenshot helper's incomplete popup capture was found only in integration;
capture now reads the actual backbuffer before SDL_RenderPresent. This is why
passing mock tests never counted as a game demonstration.

## Known limitations and prioritized backlog

1. **Native activities and unsupported error screens.** Pause stops future remote
   dispatch, not an already-started CDDA activity. Long native travel can run
   between bridge boundaries. An upstream `vehicle::remove_part` out-of-map-bounds
   error at vehicle.cpp:2235 displayed a raw debug screen outside supported
   contexts; the viewer became stale and observe timed out. Native Space dismissed
   it, after which the zombie prompt was handled. Do not claim unattended travel
   or universal popup coverage. Next scope: explicit interrupt protocol and
   observational error-screen reporting, with native regression probes.
2. **Planner dependency.** Codex chooses goals and interprets screens during an
   active chat. The server alone is not an autonomous agent. No OCR, trained VLA,
   combat policy, general long-horizon survival or API-key service is implemented.
3. **Conservative walk.** Cardinal only, maximum 8 steps, no visible creatures,
   tiny terrain whitelist, empty furniture. No structured damage/trap guarantee.
   Manual primitives and native activities need visual supervision. Next scope
   should follow measured failures, not silently loosen the guard.
4. **Scope and portability.** One game/controller; pinned stable macOS build tested
   on this Mac. No Linux/native CI or older-macOS claim. Revisit Linux for parallel
   unattended evaluation; browser-native delivery only if requirements change.
5. **Retention.** Journal and demo evidence persist project-local. Native bridge
   keeps 120 frames per process; old-process files and journals need deliberate
   local pruning after sessions end. No global cleanup or automatic save deletion.
6. **Action bindings.** Only single-key bindings are supported. This profile's
   unbound quicksave was rejected; normal Save/confirmation worked. The action
   list advertises registered actions, not a guarantee of a usable binding.

Research refresh: controller redesign or release when evidence is older than
90 days. Update contracts/tests with behavior changes; retain new failure evidence
and retire rules that add no value. No recurring automation was installed.

Initial stock launch and pkgconf installation were corrected after isolation
steering. The retained Homebrew metadata refresh and exact cleanup are recorded
in environment.md; no claim that the global environment was never touched.

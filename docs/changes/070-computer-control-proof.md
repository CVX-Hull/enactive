---
owner: lead
status: historical
date: '2026-10-29'
scope: Implemented isolated #181 enabler and reviewed #176 handoff; not the production cutover
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

## Reviewed production handoff

The following map is the reviewed #181 handoff. It is a target plan for #176,
not a declaration that those current contracts have migrated. The live Issue owns
subsequent scope and estimates. Exact implemented proof shapes/tools live in
[protocol.py](../../experiments/computer_control/protocol.py) and
[mcp.py](../../experiments/computer_control/mcp.py); the
[experiment usage guide](../../experiments/computer_control/README.md) owns build/run
instructions, and the
[closed evidence](../acceptance/2026-10-29-basic-computer-control.md) retains all limits.

## Coordinated production cutover for #176 (selected plan, not delivered)

Implement one current product contract, using the proof's mechanics as evidence.
Do not ship the experiment beside the old product dispatcher. The lead integrates;
mechanical input has one runtime owner. Optional player helpers cannot veto a basic
key or become mandatory menu state machines.

| Current producer/caller | Production disposition |
| --- | --- |
| `native/cdda_harness.{h,cpp}`, semantic hooks in `tools/patch_game.py`, `harness/controller.py`, `harness/prepared_app.py`, `tools/prepare_game.py` | Replace native7 scene/action/category/receiver/recovery authority with the reviewed SDL pixels/events shim. Retain only necessary build/platform patches. Build the sole prepared launch with explicit project userdir/windowed hints and no old bridge export/hooks; qualify that rebuilt game and its effective mechanical input options. The legacy preparation sets ENABLE_MOUSE=false and the old bridge overrides it; the new substrate must not preserve that game-specific override. Select normal application mouse configuration through preparation/player UI, record it and qualify real widget effects, rather than mistaking delivered SDL events for application support. Move experiment source into its final mechanical module and remove the experiment entry points in the same cutover. |
| `harness/native_process.py`, `harness/mission_runtime.py`, `mission_activity.py`, `mission_recovery.py`, `gameplay/{semantic_controls,ordinary_input,native_input,native_receipts}.py` | Keep exact owned subprocess/window, single writer, immutable request/result IDs, original limits, Pause/cancel, delivery uncertainty and cleanup. Remove game-root/scene/menu/activity/lifecycle/identity conditions from launch and ordinary input. Delete semantic dispatch/recovery paths; player interpretation has no harness capability. |
| `harness/{__main__,mission_client,mission_lifecycle,mission_handoff,movement}.py`, `gameplay/{mission_requests,lifecycle,interaction,interactions,navigation,skills,supervisor,input_contracts}.py` | Remove public action/walk/semantic recovery and mission-phase request producers. Replace command/client/handoff custody mechanically; move reusable game routines to optional player code only. No adopted-normal-play requirement for basic input or actor handoff. |
| `gameplay/{mission_contracts,mission_ledger,contracts,evidence,source_contracts}.py` | Replace mission/11 and DB13 current admission/readers with mechanical session/operation/receipt/frame records. Use SQLite transactions/constraints and ordinary atomic files; no shadow journal framework. Preserve attempted/unknown effects and source linkage. Success is never inferred from delivered input or process0. |
| `harness/{player_tools,player_mcp,player_view,server}.py`, `tools/{configure_player_tools,campaign_player,campaign_run}.py`, `tools/player_host/{host,run}.mjs` | Expose only the basic controls and player-owned memory/program/context services. Migrate tool schema, source/image/result routes and host handoff readers together; remove semantic skill/lifecycle/claim/readmit tools and player-view/5/mission11 assumptions. Keep fixed route, bounded HTTP attempts, provider telemetry and secret-free MCP env. Handoff changes actor custody only, not game phase/identity. |
| `gameplay/{program_input,policy_program,procedures,procedure_library,procedure_archive}.py` | Keep bounded sandboxed local execution and original per-run limits. New programs consume actual image bytes/references and player-supplied optional interpretations, then propose only basic controls; yield uncertainty to the player. Delete required category/scene/input-receiver program-view/2 projections and procedure/3 native7/mission11 execution pins. CPU/time bounds are mechanical; game preconditions/applicability remain fallible program data. |
| `gameplay/{memory_contracts,mission_memory,campaign_memory,cdda_memory,cdda_identity,cdda_timeline,advisory_capture,advisory_export}.py` and context/reflection callers | Preserve source-linked assertions, quantities, Work, correction/lineage and game/version applicability in the playing system. Remove authenticated game identity/turn/save proofs from input authority. Any visible interpretation/time estimate must identify player provenance and uncertainty. A memory assertion cannot grant custody or certify Save. |
| `web/{app.js,index.html,style.css}`, spectator/current evidence readers and `tools/{evaluate,host_analysis,observer_analysis}.py` | Show real pixels, mechanical delivery/ownership/Pause plus separately labelled player claims. Preserve source correlation and missing timing endpoints. Apparent useful-goal assessment remains human/independent analysis; no semantic success gate in the dispatcher. |
| `tests/`, `tools/{check,ci}.py`, native fixtures, `docs/{architecture,protocol,controls,player-guide,overview}.md`, affected `docs/contracts/`, component and operating guides | Replace current fixtures/contracts/readers together; retain historical reports as historical. Check strict old-format rejection and no old runnable routes. Update the overview-to-player/runbook reader path and actual control coverage, with all failed/unqualified lanes visible. |

Paths abbreviated `gameplay/` above are under `harness/`. The map names responsibility
owners; it does not require preserving every module. Delete modules that have no
remaining responsibility instead of leaving forwarding wrappers.

### Replacement and persisted-data decision

The proof defines the mechanical target/request/receipt shape. Production must add
one strict mechanical session admission (owned native/config/source, target/session,
original limits) and operation/frame evidence index; it must not add world/character,
menu/root/activity, game-time, goal or save assertions to that authority. Final product
schemas are frozen together in #176 before callers change. The proof's version1
names are not permission to accept native7/mission11 or mixed persisted records.
Player memory/procedure/program-view and host handoff formats receive explicit new
versions when their fields change; unsupported old executable formats are rejected,
not guessed or passed through. No runtime version negotiation or migration shim.

Selected data treatment: stop old writers, retain old ledgers/memory/procedures and
unknown receipts unchanged as archival evidence; start a fresh current mechanical
store. Preserve the authentic upstream game save and load it only through visible
controls. Do not silently convert old mission authority or executable programs.
Selected historical knowledge may be explicitly recreated by the player as current
fallible assertions with original source links; any old program remains inert until
the player authors/reviews a current-format revision. This is justified recreation,
not deletion of campaign knowledge or reinterpretation of an unknown effect. No new
one-off converter is needed for this cutover. Retire `ProcedureLibrary`'s old-format live importer and
`tools/export_procedure_library.py` plus its runtime advisory readers. For historical
inspection, retain ordinary original JSON/PNG and SQLite databases read-only at their
existing paths, their manifests/hashes, and the exact historical Git source checkpoint
for offline interpretation if needed. Ordinary SQLite read-only access is sufficient
for original rows; no archived launcher/controller may run or recover custody. Current
recreation receives explicit inert text/image source references, never an old executable
record or an old validator loaded into the new runtime. Preserve original links or an
explicit archival relocation manifest; do not silently move/delete their targets.

### Known format and storage cutover inventory

| Current format/readers | Disposition in the coordinated cutover |
| --- | --- |
| native7; mission/11; DB13; gameplay/2 and cdda-visible/1; evidence store/6 (`controller`, mission runtime/ledger/contracts, evidence/source readers) | Retire as current input/evidence authority. New mechanical session/operation/frame schema and fresh SQLite store; archived originals only. |
| player-view/5 (`player_view`, tools, host handoff, web); program-view/2 (`program_input`); procedure/3 and campaign-memory/6 (procedure/memory modules) | Revise together for basic pixels/receipts, player-owned assertions/program applicability and context handoff. Reject old executable/current-format admission. |
| reflection/3 and facts-procedures-reflection/3 (`mission_reflection`, reflection, mission/client/player tools) | Replace mission/native-dependent request/source fields with new player-side records. Keep bounded candidate-only advice and provenance, never dispatch authority. |
| advisory-export/data/source/capture/request/native-input/native-ack/1 and procedure-import/1 (`advisory_export`, `advisory_capture`, procedure library/archive) | Retire current import/export execution paths and keep existing exports as inert historical artifacts. No transparent conversion or old reader in the new runtime. |
| campaign-run/1 (`tools/campaign_run.py`); observer-timing/3 (`web/app.js`, `tools/{evaluate,observer_analysis}.py`) | Revise run manifests for the sole mechanical route and timing joins for new frame/request IDs. Reject old packages as launchable current data; old reports stay historical. |
| pi-player-host/4 route (`tools/player_host/host.mjs`) and host-analysis/1 | Keep the provider/HTTP telemetry contract if its fields are unchanged; remove embedded mission/player-view handoff parsing and revise affected validation tests. New source/frame joins cannot silently relabel historical records. |

Storage: preserve old `.runtime/bridge/` inbox/claimed/admissions/control-admissions,
`.runtime/mission-requests/`, `.runtime/reflection-commands/`, `.runtime/missions/`
(including mission SQLite/evidence indexes/frames), `.runtime/campaigns/` frozen
packages/reports and `.runtime/procedure-library/`. After closing all old writers,
choose a fresh explicit current session root under `.runtime/computer-sessions/`
and a fresh player store. Never discover or drain the old inboxes/stores from a
new launch. Both namespace selection and strict format rejection are tested before
native launch. Shared game lock remains a mutual-exclusion mechanism, not old
input authority. `.runtime/user/` authentic saves stay owned by the upstream game.

### Integration order and acceptance

1. Freeze the new mechanical and player data contracts, verify all callers against the producer/format
   inventory above, and stop affected writers. Record/archive existing stores and
   engine save provenance; reject mixed state before native launch.
2. Integrate native/launcher/controller, session admission/ledger/evidence and MCP/
   Pi/custodian/spectator as one source branch. Remove old dispatch hooks/tools and
   migrate all current readers. No intermediate mixed deployment.
3. Integrate player program/memory/context/handoff under the new versions. Retain
   original provenance and explicit historical uncertainty. Reuse the maintained
   Pi sandbox and SQLite/OS contracts; no alternate game-control owner.
4. Run focused real-component negatives and early frozen organic gameplay on a
   committed coherent checkpoint. Let useful goals, interruptions, routines and
   recovery occur naturally. Then independent review, full protected PR/main and
   required native/graphical evidence before product cutover. Delete the isolated
   proof entry points; update docs and retire obsolete fixtures/current formats.

Rollback means a coherent earlier source/data deployment after all new writers are
closed, never reading the new store through old code. Retain both evidence sets and
normal saves; no replay or authority reconstruction.

Original gaps stay owned by #284/#191: actual real window/output/viewport resizing,
non-unit click mapping, stale/current pointer mapping under that change, non-spatial
keys and real-human takeover, plus actual pointer/widget effects and Unicode consumption in actual widgets. Case002 delivered pointer events while the inspected legacy game option disabled mouse; identical before/after frames do not qualify a click effect. The hidden
SDL fixture only covers unit resize and simulated unowned-event takeover. Logical
renderer transforms are currently unsupported. Name and exercise a representative
second real CDDA-class game before family support; broader games remain a direction.
#164 responsiveness, #177 learning and #145 survival retain their original criteria.

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

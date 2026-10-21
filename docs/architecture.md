---
owner: maintainer
review_trigger: Boundary, authority, supported behavior or deployment change
status: active
---

# Current architecture

Current source contracts are native5, mission/9, campaign-memory/4, gameplay/2,
evidence archive4 and mission ledger11. One MissionRuntime owns the live mission API.
The prior wire4 binary has a [windowed menu qualification](acceptance/2026-10-20-native-presentation.md);
normal-game lifecycle and independent mission acceptance remain separate gates.
Start is source-free and cannot adopt an unrelated already-running character. The
registered lifecycle must verify owned launch and admitted world/character before
normal-play authority or a game-time anchor can be established. This is not yet an
accepted autonomous survival service. Earlier [foundation](acceptance/2026-10-17-foundation-implementation.md)
and [MVP](acceptance/2026-10-17-mvp.md) reports retain their dated contract scopes.
Protocol version: 5.

The [independent024 result](acceptance/2026-10-21-independent-supply-shelter.md)
exercises the integrated supply/shelter, durable memory, actual fresh successor and
normal same-character lifecycle path on deciding source502ca0f. It is bounded
development evidence, not unattended seven-day survival or learned-procedure
support. Final publication/CI and the [prospective seven-day assessment](acceptance/2026-10-21-independent-seven-day-readiness.md)
have separate gates. Earlier qualifications below retain their historical scope.

[Delivery057](changes/057-discovery-learning-campaign.md) now adds source for
ordinary key/text/click discovery and source-linked procedural memory. It retains
the existing mission writer, native input transport, SQLite history and image
archive. A root's explicit procedure selection joins its actual child inputs and
results automatically; adoption remains a player judgment over scoped data.
The historical library reads pinned closed archives without restoring old-world
facts or execution handles. See [the current contract](protocol.md#ordinary-discovery-and-procedure-data).
The new native binary has passed its local build; graphical qualification remains
pending. Reflection data/mailbox and durable bookkeeping are implementation
components; software scheduling, adapter integration and actual overlapping play
are still pending. None establishes real procedural learning or a new campaign.

The harness-enabled SDL ImGui context uses the library's steady text-caret setting.
It preserves exact image validation without treating cosmetic blink as stable
pixels. Game options and non-harness rendering retain upstream defaults.
[Native004](acceptance/2026-10-20-native-receipt-order.md) qualified unchanged
world-name captures and ordinary text/confirmation on its identified binary;
that probe did not qualify normal character lifecycle or selector/activity behavior. The
[earlier editor failure](acceptance/2026-10-20-native-editor-caret.md) is retained.

The spectator's existing serialized status poll schedules250ms after a completed
response during active play/operations,1000ms when idle or disconnected. Image
decode/sequence and authority guards are unchanged. This improves presentation
cadence; [latency targets](evaluation.md#latency-budgets-for-interactive-play) require
separate native/browser measurement and do not infer model performance.

## Coordinated change

All project-controlled boundaries follow
[S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration):
one current contract, with producers, consumers, persisted formats and guidance
migrated together. There is no runtime compatibility layer or downgrade. Current
native wire v5, gameplay records `gameplay/2`, evidence store version 4 and build
manifest version 1 name separate contracts, not alternate versions of one interface.
Historical artifacts are retained as evidence without being accepted as runtime input.

## Scope and responsibilities

The [overview](overview.md) provides the user-facing system picture. One local
macOS game and one controller are supported. Prepared keyboard-driven launch
requires project-local `ENABLE_MOUSE=false` and `FULLSCREEN=no`; native-image
validation and keyboard/user Pause remain unchanged. The wrapper requests SDL
background startup without activating the shown window, so launch should leave
the user's typing in their current app. These are child-process hints, not global
Mac settings; direct OS focus telemetry is not exposed by the harness.
The designated active Codex player
chooses plans, interprets visible outcomes and requests bounded semantic operations.
It uses the single [mission ingress](protocol.md#integrated-mission-lifecycle).
The lead owns admission, source integration and final verification. The user retains
Pause and native takeover. Role assignment is procedural, not operating-system isolation.

An eligible request's internally inconsistent source metadata, invalid extra
informing-source selection or unsupported native-row menu representation returns blocked
before phase mutation or native refresh. Its original limits and authority stay
unchanged; real authority/evidence faults still stop. The
[binding contract](protocol.md#skill-request-binding-errors) defines this narrow
case and programmatic request construction. It adds no executor or alternate API.
The pure client producer combines selected retained context with semantic intent
into that same contract. It owns no live state or source selection; receiver guards
remain authoritative. A project-local stdio MCP adapter now exposes structured
intent, bounded result collection and actual images over this same HTTP ingress.
The official SDK owns MCP framing; no new executor, schema framework or history
store is added. Current receiver schemas describe tool arguments. Disposable
snapshot/source handles retain explicit choices; stable request files fence a
second submission and the existing ledger owns results. Exact indexed archive
readers keep historical images available after bridge eviction without observing
or refreshing authority. [The integration brief](changes/051-structured-player-tools.md)
records the reuse choice, bounds, maintenance and separate host/native gates.
The [source/setup report](acceptance/2026-10-20-structured-player-tools.md) records
the synthetic/SDK checks and actual active-host limitation.

Memory assertions and their combined views have separate bounds. A `WorkView`
retains all coherent premises, including conflicts, rather than forcing history
back into one assertion's eight-source shape. Handoff uses a complete required-Work
packet and checks its finite fit before relinquishing the player lease. Work
updates then freeze until successor claim/readmission. Ordinary queries remain
small; unavailable support stays unknown. The [replacement contract](protocol.md#quiescent-player-replacement)
owns the exact source/byte bounds and later evidence-loss limits.

| Boundary / owner | Input and output | Authority and failure behavior |
| --- | --- | --- |
| Lead / active Codex chat | Objective → frozen admission, reviewed source and acceptance | Owns shared runtime and integration; no ordinary gameplay rescue in the deciding mission |
| Designated player / general-purpose agent | Visible evidence and memory → typed mission requests, plans and verification | One bounded actor; fresh-context handoff needs quiescence and one-use accounting; no authority from a summary |
| Structured player adapter / harness maintainer | Explicit semantic arguments and returned handles → existing ingress, settled result and exact PNG | No capability, source refresh, replay, automatic Resume or new ledger; actual host review-free proof remains separate |
| Mission runtime / harness maintainer | mission/9 request → operation receipt and cached observer status | One writer and queue; exact lease, original root/child budgets, durable intent before publication; unsupported adapters block |
| Controller / harness maintainer | State-bound command → native request and correlated receipt | Serialized ordinary/control writers, exact process-local lease, Pause revocation and native fences; never edits saves |
| Native bridge / integration maintainer | Bounded request → actual input, visible metadata and rendered frame | Engine validates outcomes on its game thread; unsupported boundaries cannot claim success |
| Spectator / viewer maintainer | Frame and mission snapshot → inspectable progress, uncertainty and Pause | Mission Observe uses typed ingress; raw input/Resume/recovery disabled while nonterminal; malformed state stays locked |
| Campaign evidence and memory / harness maintainer | Original sources → bounded claims, unfinished Work and context packet | SQLite journal and retained frames; corrections/loss prevent resurrection; historical facts never become current input authority |
| Owned-process adapter / harness maintainer | Fixed prepared wrapper → retained child and process facts | No arbitrary command, PID adoption or signal interface; process exit alone proves neither save nor identity |
| Setup / build maintainer | Pinned sources/toolchain → isolated app and manifest | Windowed, explicit project userdir; no global installs or automatic game launch |

Implementation: [mission runtime](../harness/mission_runtime.py),
[contracts](../harness/gameplay/mission_contracts.py), [ledger](../harness/gameplay/mission_ledger.py),
[campaign memory](../harness/gameplay/campaign_memory.py),
[navigation](../harness/gameplay/navigation.py), [native-row menus](../harness/gameplay/interaction.py),
[interpreted controls](../harness/gameplay/semantic_controls.py),
[item selection](../harness/gameplay/interactions.py),
[controller](../harness/controller.py), [server](../harness/server.py),
[native bridge](../native/cdda_harness.cpp), [viewer](../web/app.js),
[evidence store](../harness/gameplay/evidence.py), [owned process](../harness/native_process.py).

Navigation, native-row focus and fallible image controls share the same mission
writer. An ordinary interaction, item, activity, inspection or interrupted navigation root may own a returned prompt. Explicit control
children retain its original scope, actor/epoch, deadlines and cumulative input
ceiling. A settled owned menu may be refreshed only through retained exact-PNG
source revalidation. Typed PhaseReceipt audit data restores no private phase on
reopen. A normal return closes the prompt without proving the desired effect.
Returned navigation into an ordinary same-session menu retains its verified route
prefix and last verified position, with no movement credit for the menu-opening
input. Explicit menu/editor children remain under the original root,
including after a recovered suffix; no automatic answer or route retry occurs.
After normal return, the player can choose a new plan from current evidence.
Cancellation selects one exact registered action: TEXT.QUIT for STRING_INPUT,
UILIST.QUIT for UILIST, WORLDGEN_CONFIRM.QUIT for WORLDGEN_CONFIRM_DIALOG, otherwise
QUIT. A rowless POPUP_WAIT with exactly ANY_INPUT/COORDINATE after excluding the
pinned producer's ubiquitous toggle_language_to_en instead uses one existing SPACE
key. Registered QUIT retains cancellation; other missing/extra controls or rows
block without guessing. Exact-image preflight and original phase limits still
apply. The result is partial for verification and never answers a later question
implicitly. Supporting
one worldgen cancel action does not implement the whole setup-abort workflow.
Typed item selection/count/commit and registered inspection have synthetic runtime
coverage. Quantity editing belongs only to the item phase whose returned
MARK_WITH_COUNT opened it. Native007 qualified the selected counted drop/pickup
path; other selector semantics require their own actual evidence.
An owned activity poll advances through one bounded observation, including native
output menus or normal return; no poll sends input or certifies sleep/output.
Activity control transport preserves terminal ACKs before persistence and sends no
Resume. A registered private activity phase now composes internal stop, exact
interruption/answer and separately charged Resume in source. Unknown delivery stops;
known ACKs remain delivery evidence without a frame. Actual native qualification
remains open; already-returned uninterpretable semantic outcomes stay stopped.
World-generation forms have no tab-focus mapping. On the final character-description
screen, NEXT_TAB begins character completion and is blocked as ordinary focus;
returning to a previous tab remains available. World FINALIZE and character finish
use explicit registered lifecycle stage commits, separate from ordinary focus.
Interpreted activation of the selected world Finish row returns a correctable
zero-input result directing the player to its existing create stage commit; it
keeps the lifecycle phase and original limits available.

Ledger10 records Resume under admitted lifecycle/readmission or an exact activity
resume child, and charges activity controls through the same primitive table.
Prepare and reopen share parent/answer rules; prior ledger formats reject unchanged.
The controller's trusted Resume compares controller boot, operator-Pause counter,
general generation and current native evidence. Expected internal revocation cannot
erase an intervening user Pause. Exact-PNG controls additionally compare verified
encoded frame bytes; native-row/navigation controls require native-state equality.
Prepublication callbacks retain source and durable intent outside the controller's
data lock, then all authority/deadline fences are checked again. Unknown delivery
retains its pending identity and charge; it is never blindly replayed.

After a committed create/load transition, a still-paused identity phase supports
diagnostic Observe under its exact historical effect and live owned lineage.
This refreshes evidence without activation or a lease. The existing ledger proof
validator is reused, including before explicit readmission activates the ledger.
A premature exact identity inspection can instead return a zero-input missing-step
explanation after proof, source/image, ownership, quiescence and original resource
guards; the private paused phase stays intact. It neither refreshes an aged source
nor grants a lease. A new explicit same-root create/load lifecycle call separately
charges Resume before inspection; genuine faults still stop. Only the diagnostic
checkpoint advances during Observe, while first-normal
provenance, original budgets and the separately charged explicit Resume remain.
No phase is reconstructed from historical records on reopen.

The selected mission game-time cap gates every input dispatch lane, including
lifecycle, exit and readmission. Rejection settles any reserved intent before
revoking authority; controller preflight does not revoke while its lock is held.
Unadopted startup has no canonical game clock and retains its separate finite
guards. Observe and user Pause remain available without input. The software
ceiling is eight days, the default remains 12 hours, and each admission selects
its own finite cap and ending headroom. No cap grants cleanup input once exhausted.

A lifecycle question interpretation that fails local shape/exact-text validation
returns a blocked request before refresh, rotation or dispatch. The original phase
and deadlines remain; this result neither attests fresh pixels nor grants a lease.
A new corrected request passes the full existing source/authority/image guards.
Points-stage installation follows complete validation. Other errors and unknown
delivery retain their stopping behavior. This uses the existing blocked result
and single writer, without a second retry service or compatibility path.

Start/Observe cannot seed identity or the mission clock from an unowned game.
Unexpected normal sources stay diagnostic across reopen; one explicit adoption gate
protects time, map and native-memory eligibility. Some core tests assume identity explicitly; the new lifecycle integration tests
exercise the real adoption reader without that mock. Registered creation/save/load
and provisional character inspection are composed in source. Quiescent handoff, bound
successor context retrieval/claim and separately charged readmission also compose in
source; historical receipts restore no live consent. Selected item/activity and ordinary
inspection adapters compose through the same writer. Normal finish now
composes in source after committed normal exit, preserving historical evidence
and distinguishing cleanup from player-reported objective completion. Source coverage alone does not accept a native
mission. Registered launch now composes the fixed process adapter
with original deadlines and fresh paused-menu readiness in portable fixtures.
Launch sends no Resume/input and establishes no identity or game-time anchor.
Registered untouched-menu exit composes charged Resume/QUIT with an explicit
player-interpreted confirmation, original operator mark and shared root/child limits.
Published Yes plus exact owned normal exit and narrow durable pending retirement
can resolve process custody while retaining an unknown ACK and all charges. No
normal save is claimed by that untouched-menu retest. The [bounded native retest](acceptance/2026-10-20-owned-launch.md#native-qualification002-accepted-owned-menu-component)
qualified the Yes/normal-exit path while retaining its failed first attempt. It
created, loaded and saved no character and did not exercise native No or user Pause.
Registered creation, normal save, saved-menu exit and new-child exact reload passed
the scoped [Native007 qualification](acceptance/2026-10-20-native-lifecycle-qualified.md).
The later [independent024 mission](acceptance/2026-10-21-independent-supply-shelter.md)
exercises that lifecycle within the full supplies/shelter outcome; component
qualification alone did not accept the mission.
The [timeline reducer](../harness/gameplay/timeline.py) sums normal-session spans
only with exact chronological equal-turn endpoint links across sessions. The [lifecycle reader](../harness/gameplay/lifecycle.py) derives links only after
validating owned transitions, direct identity Claims, inspection receipts and saved
endpoints across every retained normal session. These links grant no permission.
The runtime validates a candidate adoption before committing its immutable result,
then verifies the committed history before publishing a normal binding/map. Reopen
can recover historical cost but no live phase, process or lease.
Missing continuity makes cost unknown instead of silently resetting it.

Lifecycle Resume, explicit creation-stage commit, normal save, identity inspection
and owned exit confirmation refresh the selected checkpoint once at entry inside
the operation, comparing exact retained native state and PNG bytes under the
original actor/Pause and root/child deadlines. Resume journals source lineage before
acquiring a lease; it cannot construct authority from an old binding. Exit's typed
revalidation links the immutable interpretation to the actual dispatch source at
write, orphan-proof validation and reopen. Save refresh precedes operation rotation
and preserves the original normal-game time anchor. [Native qualification001](acceptance/2026-10-20-lifecycle-freshness.md)
retains the timing failures and successful normal stopped cleanup; the source
repair is not a character-lifecycle or independent-mission pass.

Live native comparisons tolerate only capture/transport id, timestamp and filename
churn, reusing EvidenceStore's state comparison without archiving passive polls.
Observe keeps its exact response/original receipt; image and input-authority checks
remain separate. A proven returned-Resume-only startup can adopt a fresh internally
paused copy of the original menu for a separate normal cleanup root. Ledger audits
its immutable input lineage; runtime/store verify pixels and live custody.
[Native006](acceptance/2026-10-20-native-character-lifecycle.md) established
ordinary creation/identity, counted dropping, native wait/poll and normal first
save/exit, then stopped before reload and exceptionally closed its new child.
Its actual blockers drive one repair batch: known non-HOSTILE movement,
engine-scoped actionable inventory rows, actual MAIN_MENU→UILIST reload staging
and narrow Resume-only create/load abort. The abort revokes authority without
input or rebasing the launch; separate Observe/new exit verifies the paused menu.
Unique enabled selected admitted-character evidence is checked before reload
dispatch. No fictitious label, prior-child save or historical proof grants input.
[Native007](acceptance/2026-10-20-native-lifecycle-qualified.md) subsequently
qualified actual known movement, counted pickup, normal reload and final stopped
Finish at the rebuilt native. Independent read-only audit verified all287frames
and retained112charges/six unknown ACKs. Explicit #156 readiness still precedes
the real deciding player/successor mission; scoped engineering evidence is not
independence acceptance. Earlier setup reports
remain linked evidence, not current implementation instructions.

The [first actual deciding attempt](acceptance/2026-10-20-independent-mission-first-attempt.md)
failed on a paraphrased world question before Yes input; its exceptional cleanup
and 70 returned inputs stay retained. The separate actual spectator Pause test
passed live phase/lease revocation and stale-request rejection. It qualifies no
in-flight cancellation or post-Pause readmission.
[Native008](acceptance/2026-10-20-confirmation-correction.md) subsequently qualified
both world/Save local rejections and new exact corrected requests, visible identity
and normal save/exit/stopped Finish through a fresh engineering operator. It
retains three unknown ACKs with reconciled effects and no gameplay objective.
The synthetic hosted clock-fault fixture was corrected without changing production
dispatch checks; subsequent common and exact hosted CI passed. Later independent
failures remain linked from [the work map](work.md).

Cached status performs no evidence or memory I/O. It can show the last explicitly
requested context packet, including claims, Work, source IDs, omissions and
dispositions. That packet is historical as of its ID; rendering neither recomputes
it nor turns it into current evidence. Unmeasured model cost/latency remains unknown.
The writer also caches SQLite-derived cumulative request/admission groups and
the live private activity checkpoint. The viewer separates that checkpoint from
historical results and makes query-specific memory corrections, unfinished Work,
source dispositions and omissions readable. It introduces no retrieval/executor
or second counter store. Known nondelivery does not invalidate memory premises;
source freshness, scope and unknown-effect checks still apply. The
[observer inspection](acceptance/2026-10-20-mission-observer.md) uses synthetic data,
not native mission evidence.
The private [recovery holder](../harness/mission_recovery.py) now preserves an
unknown dispatch's original custody and evidence reservation. It collects actual
controller delivery evidence once before Observe can overwrite it, through the
existing files/journal and bounded process-local references. A framed late result
is archived against its original reservation before diagnostic Observe. Collection
restores no authority and leaves the ledger unknown. Explicit reconciliation now
checks typed proof against the independently retained original dispatch receipt
and a fresh paused diagnostic source. Separate normal-play readmission charges
one Resume. Navigation continuation retains the original goal, Work, game-time
anchor and cumulative root limits; competing roots and handoff remain fenced.
Reopen validates historical proof but restores no private phase or input consent.
The single current effect envelope and ledger11 reject older shapes rather than
converting them. This source integration is not native recovery qualification or
an additional executor/history store. Ambiguous delivery and unsupported semantic
uncertainty remain stopped; a later expected-looking frame cannot supply proof.
The [mission design](design/player-owned-mission.md) owns further integration and
acceptance. Portable source checks, wire4 menu qualification and actual independent
normal-game play are separate evidence lanes.

The [first seven-day campaign](acceptance/2026-10-19-seven-day-survival.md) used a
supervised external operator and supplies development evidence for this migration.
Its ordinary-input workflow and waypoint runtime are not alternate live mission
paths. Passive waypoint/planner libraries remain available for offline studies.
The earlier [two-phase operator result](acceptance/2026-10-18-campaign-operator.md)
retains its narrow consumption/conservation and handoff evidence.

The [first fresh deciding attempt](acceptance/2026-10-18-seven-day-stop.md) later
stopped at13game seconds after an approval rejection following a guarded-walk stop.
Its aggregate omitted the observation needed for the player's next decision;
native preflight alone does not supply that semantic reassessment. The
[bounded correction](changes/023-walk-reassessment.md) retains the actual last walk
observation separately from its terminal exchange and reuses the controller's
Pause/frozen/generation mechanisms. A stopped walk requires explicit fresh Observe
and Resume; the player still interprets the image and decides again. Original
partial and normal cleanup remain evidence, not seven-day autonomy.
The [targeted native probe](acceptance/2026-10-18-walk-reassessment.md) verified a
zero-step stop, frozen Resume rejection, fresh Observe/Resume and inventory/cancel;
partial-walk fault tests remain a separate portable lane. No survival progress was
claimed and the earlier unexercised load probe remains retained.

The [same-character functional continuation](acceptance/2026-10-18-seven-day-continuation-stop.md)
then stopped correctly on readable unsupported LIST_ITEMS. Ordinary native menu
coverage now includes nearby lists, crafting and construction; a scoped query marker
retains original generic bindings only at pinned direction/item-detail/comparison
input calls. Unknown contexts remain unsupported. [The qualified native proof](acceptance/2026-10-18-ordinary-menus.md)
verified item examination/comparison and crafting/construction entry/cancel, then
normal Save/Quit. Its first renderer failure remains retained; direction-query
regression and post-shutdown reload were subsequently verified by a
[separately scoped gate](acceptance/2026-10-18-menu-gate.md). Neither earlier cleanup exception
grants standing fallback authority.

## Runtime and state

Observe → choose a bounded action → validate current session/revision → dispatch
at an eligible engine input boundary → observe the next boundary → interpret the
result. A prompt is a valid outcome. `ready` means returned to input, not objective
completion. A timeout produces an unknown outcome and freezes further actions.
Observe/reconcile then explicitly resume; never automatically replay the input.

Native keyboard/button input latches takeover. Pause prevents subsequent remote
dispatch; it cannot cancel an already-started engine activity. Explicit operator recovery can request the native activity query, answer
its exact owned prompt, or deliver one Space at the current raw debug prompt.
These operations stay paused and preserve the original gameplay outcome. The
spectator, CLI and separate authenticated recovery endpoint expose them without
waiting for the ordinary gameplay writer. A service restart revokes durable input tokens and retains unfinished
admissions as unknown without replay. World entry/exit, including same-process
save/reload, invalidates old session and relative-position authority. Full details:
[protocol and guarded play](protocol.md).

## Action and recovery views

These are **current behavior** explanations for the operator and maintainer;
[protocol](protocol.md) owns the detailed contract. They summarize the implemented
flow, not a new API or fresh native verification.

### What happens when the agent acts?

![Current action sequence: observed authority is checked before input; a ready response requires interpretation, while a timeout freezes dispatch.](diagrams/action.svg)

Read top to bottom: vertical columns identify responsibilities; solid arrows are
requests/input and dashed arrows are observations/results. The two alternative
outcomes are mutually exclusive paths for this request. The controller obtains
current authority but rejects a stale planner choice instead of silently updating
it. The native bridge validates again before delivery. A rejection dispatches no
input. The eligible next boundary can be a prompt: `ready` does not prove success.
After timeout, observe to reconcile and explicitly resume; never replay blindly.
The spectator shows the returned frame/state. [Editable sequence](diagrams/action.mmd).
The native commit check includes the positive boundary, matching rendered frame
and durable host token; a later Pause cannot reverse that committed input.

### How do I recover control?

![Current recovery workflow: reconcile after startup, uncertainty or a stopped walk, remain paused, explicitly resume, and pause or take over when needed.](diagrams/recovery.svg)

Rounded boxes are operator workflow states; arrow labels are the conditions that
change them. The initial dot marks controller startup/restart; attached notes
state limits. This is a workflow summary, not an exhaustive combination of internal
flags. Paused dispatch can coexist with an unresolved input; its timeout still
requires reconciliation. Successful observation restores current knowledge, not
proof of the prior objective. Resume must succeed with current authority; concurrent
pause/takeover can prevent it. If observation fails, remain frozen and inspect the
native window; dismiss unsupported screens there if necessary. A world reload or
game restart invalidates old session authority. No arrow replays an uncertain action.

Pause/takeover stops **new remote dispatch**. An already-running game activity
may continue. Explicit recovery asks the engine to interrupt; cancellation is
never inferred from an input-delivery result. Native controls remain available. Follow the [recovery procedure](runbook.md#pause-timeout-and-recovery)
for operational steps. [Editable state view](diagrams/recovery.mmd).

## Observation and deployment boundaries

The viewer uses actual presented SDL frames, including rendered popups. Structured
scene metadata is deliberately restricted to player-visible facts; it excludes
save contents, undiscovered map data and hidden threats. See the exact observation
allowlist and routine limits in [protocol](protocol.md).

All services are local. The spectator binds loopback; it is not designed for
public network exposure. The game wrapper explicitly supplies the project userdir
and windowed settings. New packages, outputs, caches and saves stay project-local
or in the setup manifest's owned temporary build. [Setup](setup.md) and the
[environment ledger](environment.md) own installation facts and history.

## Change boundaries and verification

Keep the controller independent of HTTP/server and setup tooling; only the server
and CLI assemble it. The gameplay package cannot import controller/server/CLI, build tooling or
network/process launch modules. Its retention reservation is capacity accounting,
not an input lease. The viewer consumes the local service contract. Native game
access stays in the integration patch. Configured Import Linter dependency contracts and narrow protocol checks catch
specific source drift; review and real native probes establish broader behavior.
The [control map](controls.md) identifies implemented checks and remaining gaps.

A native bridge/input/renderer, compiler, source-pin or protocol change requires
fresh relevant native acceptance before a new gameplay claim. A documentation-only
or governance-check change does not revalidate the game. [Operations](runbook.md)
provides recovery and acceptance procedures.

Architecture decisions: [native platform](decisions/001-native-platform.md),
[serialized bridge and stack](decisions/002-local-contract.md). Re-evaluate their
assumptions when scope changes. Current architecture is authoritative about what
exists; superseded decisions and dated reports remain historical evidence.

## Separate recovery and memory boundaries

The [recovery contract](protocol.md#explicit-operator-recovery) keeps the control
inbox, duplicate ledger, durable admissions, pending slot and unknown history
separate from ordinary gameplay. The game thread consumes both. Recovery cannot
bypass native interruptibility, own an unrelated confirmation, or resume gameplay.
The [recovery flow diagram](design/native-control.md#user-visible-design) shows
request, exact prompt, uncertain outcome and reconciliation paths.
One controller process lock covers both host writers; revocation and admission
share the data lock. Native validates its current prompt and the host token again
at input commit. Delivery after that gate cannot be undone by a later Pause.

Task memory composes the evidence store; it has no controller dependency or frame
copy of its own. Explicit refresh retains facts, while snapshots revalidate
bounded existing records. Source disputes preserve historical uncertainty; a
process-local store generation prevents intervening invalidations from disappearing
when an earlier frame returns. Candidate validity is advisory data, not dispatch
authority. Retirement/restart never reconstructs an execution lease. See the
[bounded memory contract](protocol.md#passive-task-memory) for ceilings and costs.

## Bounded planning without execution authority

The [planner port](protocol.md#bounded-injected-planner) accepts an immutable task,
visible evidence and caller-supplied capabilities. It invokes trusted injected
provider code with serialized data, validates a returned candidate and accounts
for the call. It owns no controller, dispatch lease or recovery tools. There is no
concrete model provider connected to the service.

One task run owns one port, one physical provider slot and its original admission
clock/start evidence. Cancellation and stale results permanently remove candidate
applicability; late completion can update accounting only. A provider that ignores
cancellation occupies the slot until it exits. This bounds resource growth without
claiming that Python can forcibly terminate provider code. Independent deterministic
fixtures test this lifecycle; they do not measure model quality or native gameplay.

## Passive skill verification

The movement skill is a bounded local verifier. It returns one proposed input,
then waits for its correlated result. The caller owns authority and dispatch;
there is no background player or automatic retry. The controller's existing walk
and the skill share `harness/movement.py`, so their visible terrain/creature rules
cannot drift into independent copies. Version-3 cardinal skills verify the current
boundary at an exact credited target; eligibility for another step additionally
checks its next neighbor. Public walk retains its conservative post-step next-tile
check. Import Linter keeps that policy free of
controller, gameplay, networking, clocks and filesystem dependencies.

![One proposed step passes through caller-owned dispatch and retained evidence before progress or a stop is reported.](diagrams/skill.svg)

[Editable diagram](diagrams/skill.mmd). The [skill contract](protocol.md#passive-bounded-movement-skills)
owns identity, budgets, generation checks and failure behavior. The manual native
acceptance driver supplied the caller role; it is not a production supervisor.
The planner port still requires an explicitly supplied accepted capability tuple.

## Passive task supervision

The waypoint supervisor composes that planner, retained evidence, task memory and
movement skill. One explicit task preserves its origin, waypoint, route history
and budgets across pauses and remaining-route plans. The module offers one intent
and consumes its exact correlated result; it cannot send an input or grant a lease.
Outbound completion prompts a fresh return decision. Both verified legs and a
fresh current-boundary guard are required for task completion. Starting the return
leg still validates the actual next tile before requesting a fresh plan.

![A task alternates bound planning and one-step verification, preserving progress at stops.](diagrams/supervisor.svg)

This passive-component diagram answers “Where do feedback and correction happen
in the waypoint study?”
Boxes are responsibilities/states in one serialized caller, not processes. Solid
arrows show decisions and evidence flow; the dotted edge identifies the caller adapter used by the historical study. The [editable diagram](diagrams/supervisor.mmd) and
[exact contract](protocol.md#passive-waypoint-supervision) distinguish eligible
intents from real authority. Explicit continuation verifies the remaining route;
unknown effects stay unresolved, and complete legs need verification without
another move. A new timestamp or model assertion cannot clear a nonprogress stop.

The retired waypoint runtime used this passive supervisor. It has no current
live task/planner endpoint; MissionRuntime accounts for its own typed semantic
operations and controller receipts. The supervisor package itself grants no
lease. Historical native evidence does not qualify the migrated mission path.

## Run ownership and operator takeover

This current logical view answers “Who can send the next input, and how do I take
over?” Boxes are controller/caller responsibilities in one host process; arrows
show acquisition, attempted input and revocation. Native token validation still
occurs inside the game at commit. Status is descriptive, not a capability.

![Controller run ownership: one explicit owner, competing inputs rejected, Pause revokes before returning.](diagrams/run-ownership.svg)

[Editable diagram](diagrams/run-ownership.mmd). A trusted in-process caller claims
fresh normal-play authority for navigation, or supported-menu authority for an
explicit interaction/lifecycle operation, with empty writer queues. The exact
object capability binds mission/actor/epoch, host Pause and human takeover
generations. Navigation uses shared movement guards; each action/key rechecks
the informing session/revision/boundary. External key/action/walk/resume
reject while owned. At the HTTP boundary a nonterminal mission additionally owns
Observe and recovery; use its typed request. Cached status and Pause remain available. Pause, recovery, native
takeover, transport failures and shutdown revoke the owner. Explicit release also pauses;
Resume restores transport only. Queued requests retain their original admission
generation and cannot cross takeover or acquisition. No process restores a lease.

[Protocol](protocol.md#controller-run-ownership) owns the precise contract. This
controller capability is consumed by MissionRuntime. The
[integration contract](protocol.md#integrated-mission-lifecycle) explains mission
admission, exact logical/native receipts and the spectator.

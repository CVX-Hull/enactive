---
owner: maintainer
review_trigger: Launch, control, recovery, recording or storage changes
status: active
---

# Operate, recover and retain evidence

Supported scope: one prepared local macOS game.
For fresh installation use [setup](setup.md); use [overview](overview.md) for limits.

## When a mission owns execution

A nonterminal mission owns observation/input even while paused and without a live
lease. The spectator shows objective, actor, epoch, skill, costs and source details;
Observe uses the typed mission path and Pause stays independent. Native window
input can take over. Resume cannot restore a mission lease, identity or private
phase. Unknown delivery stays unknown; a new owner does not prove success.
Player replacement uses the [typed handoff procedure](protocol.md#quiescent-player-replacement):
settle tools, request internal handoff, retrieve successor-bound memory, declare
needed source reads and claim while paused, then deliberately request readmission.
A source/packet omission must be corrected within original limits; it is not
permission to resume through another endpoint. Historical receipts cannot restore
a phase after user Pause or service restart. This path has synthetic coverage;
actual clean-context/native acceptance remains required.
Eligible lifecycle Resume, stage commit, save, identity inspection and owned quit
confirmation refresh an aged checkpoint
inside the operation under exact-state/image and original authority/deadline
checks. The player need not race a three-second window between model/tool calls.
A changed image, Pause or expired root still stops input; do not retry an unknown
delivery. [Native timing failure and retained cleanup](acceptance/2026-10-20-lifecycle-freshness.md).
Before admission, ordinary controller commands retain their documented guards.
Registered launch can only verify a retained child and paused main-menu readiness;
other lifecycle gaps below prevent independent production gameplay. A launch receipt
grants no character identity, Resume, lease or normal-game time. No actual launch
acceptance follows from portable process fixtures.

## Permissions and player ownership

See [the permission audit](operator-permissions.md) before requesting elevation
or changing executor ownership. Narrow project-local CLI rules are prepared and
matching-tested; [actual-player calls and resumed play](acceptance/2026-10-18-activity-distraction-stop.md)
verified the scoped loaded setup. A later native proof used the stable CLI without
recurring review or another restart. Changed actors/entry points/policy need their
own preflight; existing capture wrappers do not match the stable CLI rule. User keys/unlock/rescue are not the
routine fallback. A passive waypoint planner has no live ingress. A designated
player needs the explicit bounded mission assignment and handoff below; permission rules
do not establish actor identity or restore ownership.
Before admitting gameplay, have that actor perform a passive access preflight with
the required explicit tool permission mode. Lead access alone is insufficient;
see the [actor preflight](operator-permissions.md#dedicated-gameplay-context).

## Start and observe

First inspect existing terminals/processes to avoid starting a second game or
controller. A native app lookup by name may launch a second copy when the game
was started directly by its wrapper; do not use lookup as a process-existence check.
Use the existing spectator to inspect native frames when a tool cannot bind the
already-running native window.
Do not kill an unrelated service to free a port. From this checkout,
use an available loopback port and launch only the prepared project bundle:

```sh
.venv/bin/python -m harness serve --port 8766 --timeout 15
open .runtime/Cataclysm.app
```

The explicit15second native wait uses the existing bounded setting. Actual world
selection exceeded the default5second wait in qualification004; ordinary replies
still return immediately. Record the chosen value in a mission's frozen setup;
it cannot renew original root deadlines or repair an expired/unknown input.
[Latency accounting and proposed targets](evaluation.md#latency-budgets-for-interactive-play)
separate loading, skill execution, observer updates and model/tool overhead.

Launch the prepared app **bundle**, which executes that project's wrapper and
explicit userdir. Direct terminal execution of the wrapper produced a game that
native app automation could not bind in the first-day rehearsal. Bundle launch
exposed the actual window in a subsequent menu-only probe. Neither launch method
by itself proves recovery works. For an agent campaign, verify current actual
native frames, windowed configuration and control access before loading the
character; do not make a desktop UI tool's binding/unlock availability a
prerequisite for supported engine menus. A UI tool may launch the exact stopped bundle directly,
but must not use app lookup to check whether another game is already running.

Open http://127.0.0.1:8766/ to watch. Port 8766 was used for the MVP because 8765
was occupied; current availability must be checked. Observe, interpret the frame,
then explicitly resume. Read returned session/revision after every command:

```sh
.venv/bin/python -m harness observe
.venv/bin/python -m harness resume
.venv/bin/python -m harness action inventory --expect SESSION:REVISION
.venv/bin/python -m harness walk north --steps 3 --expect SESSION:REVISION
.venv/bin/python -m harness pause
```

SESSION:REVISION is a placeholder for values from the observation used to decide
the action. Resume changes revision. `ready` is an input-boundary acknowledgment,
not proof that an objective succeeded. Reinterpret prompts and new frames. The
viewer displays the recorded objective read-only. Outside a mission, the CLI
`goal` command records text without starting an agent. Mission objectives come
from their immutable admission.
A registered action can be rejected if it has no usable single-key binding. A
walk may report `stopped` after all requested steps completed; inspect `steps`
and the frame before deciding again. See the [protocol](protocol.md).

Public `walk` returns an aggregate with a nested `observation`, its phase and
original receipt clock, and a separate `terminal_response`. Inspect both: after
an uncertain input the observation can still be the pre-action image. Missing or
unavailable observations remain explicit. Capture the nested frame when retaining
walk evidence; an aggregate is not a native response packet.

Every stopped walk now leaves dispatch paused and frozen. Obtain a separate fresh
Observe, inspect its actual image and the stop reason, reassess, then explicitly
Resume before choosing the next input using its current session/revision. Status,
internal preflight and an earlier retained frame cannot substitute for this step.
Do not automatically replace a stopped walk with ordinary movement. The controller
requires Observe/Resume; it cannot prove your interpretation. Actual approval
denial still ends an investigation under its admitted stop rules; no retry,
permission expansion or actor/transport switch is a recovery around it.

Use each command's actual CLI grammar: Observe, Resume, Pause, status and goal do
not accept `--expect`; ordinary key/action/walk require it. Observe and Resume
do accept `--timeout`, subject to the admission's ordinary deadline. Consult
generated `--help` or the shared parser rather than copying
flags between commands. Keep large capture envelopes redirected and read original
numbered receipt JSON; a truncated tool display is not an original receipt.

## Pause, timeout and recovery

Pause prevents subsequent remote dispatch. Native keyboard/button input also
latches takeover. Neither guarantee cancels an already-running native activity;
use explicit operator recovery below or the native window to interrupt it. Do not spam remote keys to escape a stall.

For a timeout or frozen viewer: preserve the error/journal and last frame; inspect
the native window. Unsupported upstream error screens may need native dismissal.
Observe to reconcile current state, then explicitly resume only when interpretable.
Do not resend an uncertain action. New observations do not prove its old objective.
The agent must handle routine prompts through verified engine input rather
than requiring the user to press a key. At the explicitly instrumented common
direction query, a fresh DEFAULTMODE/menu frame supports ordinary selection or
cancel after explicit Resume; it has no gameplay scene. Unrelated DEFAULTMODE
contexts remain unsupported. If using verified desktop automation for a different
prompt, Pause remote control first, inspect the actual prompt, charge any native
input to the same accounting, and retain its result separately from remote receipts.
Never send a remote key at an
unsupported boundary, invent an acknowledgment or turn an unreadable prompt into
permission. Unavailable access or required human rescue fails campaign readiness.
An app-inventory access/lock error does not prove an existing game binding is
unusable. If an already-owned binding exists, inspect it once against the current
bridge prompt before concluding access failed; do not use app lookup to launch
another game. In [rehearsal002](acceptance/2026-10-18-first-day-rehearsal-002.md),
that binding supplied actual before/after screenshots and ordinary Shift+Y at a
sound-distraction query. Charge native input before sending it, retain its tool/
image evidence separately from a bridge receipt, and Observe afterward. Remote
takeover remains paused until explicit reauthorization. A failed/unreadable
binding stops; no user unlock or alternative OS-event injection is prescribed.
The [direction-menu acceptance](acceptance/2026-10-18-native-direction-menu.md)
records actual rebuilt-engine Escape, adjacent selection and empty-current-tile
behavior without user keys. The reuse-first desktop-tool preflight failed before
admission; this narrow support does not establish general native recovery.

For service restart: stop that service normally, start one controller, observe
and reconcile, then resume. For a game crash/restart: preserve diagnostics, follow
the bundle-based [start procedure](#start-and-observe), use normal CDDA load UI,
and acquire new session authority.
Old-session commands must not be reused, including after normal save/reload in the
same process. Native-v4 rejects older and mixed components; restart a
matching controller and native build, then observe. No save-file repair/editing is prescribed.

Input admissions are durably retained in `.runtime/bridge/admissions/` before
dispatch. An unresolved request remains unknown across reconciliation and service
restart; the current scene is not proof of its old result. Do not delete admissions
or rewrite journals to clear this condition. Preserve them with incident evidence.
At `activity_poll`, `debug_prompt` or `unsupported`, observation is allowed but
remote key/action/Resume is denied. Return to a supported boundary through explicit recovery or normal
native controls, then observe and explicitly resume. Pause only revokes input
that has not crossed the final native commit check; it cannot undo a prior input.

Use CDDA's normal Save menu before quitting. Stop the controller with Ctrl-C; it
leaves remote control paused. Saves are in `.runtime/user/`. Never treat a stale
frame or old acceptance record as proof a current process is healthy.

## Operator recovery

For activity interruption, inspect the fresh decoded activity frame and choose
Request interrupt if advertised. The control performs Pause before admission.
A committed
activity continues while paused; it may finish or enter another prompt before
recovery applies. Transport-only Pause preserves scene revision; a fresh native
probe opened the owned WAIT question without the former Pause/Observe workaround.
Preserve any rejection, observe deliberately, and decide anew; never automatically
retry. [Round 008 evidence](acceptance/2026-10-17-native-recovery-planner.md) records
the YES/NO, completed-activity, unknown-result, revocation and reload probes,
including controlled fault injection and its limits. Tutorial save-load errors
remain a separate [content defect](https://github.com/CVX-Hull/enactive/issues/47).

For prompt answers and debug continuation, use Observe, inspect the frame, and use the
explicit recovery button when eligible. An owned confirmation exposes Yes/No;
a raw debug prompt exposes one-shot continuation. Gameplay and recovery pending
or unknown records remain separately inspectable. Pause remains available during
either request. Recovery never automatically resumes play or repeats a request.

For CLI use, copy the exact evidence that informed your decision:

```sh
.venv/bin/python -m harness request_interrupt --session SESSION --generation GENERATION
.venv/bin/python -m harness answer_interrupt --session SESSION --generation GENERATION --boundary BOUNDARY --revision REVISION --frame FRAME --interrupt-request-id REQUEST_ID --choice NO
.venv/bin/python -m harness continue_debug_once --session SESSION --generation GENERATION --boundary BOUNDARY --revision REVISION --frame FRAME
```

These are alternative operations, not a sequence to run blindly. Placeholders
come from fresh observed state; old values reject rather than refresh themselves.
An operator controlling the existing Python `Controller` instance can also call
`recover`; never start a second controller to obtain this API. Obtain fresh
observation and pass its session and control generation explicitly. At an eligible
activity poll use `request_interrupt`. Inspect the actual returned owned prompt,
then call `answer_interrupt` with YES or NO and its exact boundary, revision,
frame and originating interruption ID. At a raw debug prompt, preserve the error
frame and use `continue_debug_once` with its exact evidence. This sends one Space;
it does not repair the error or suppress later ones. Exact argument names are in
the [protocol](protocol.md#explicit-operator-recovery).

Check the returned status and then observe: prompt opening and answer delivery
are different from activity cancellation. WAIT may resume backlog. Unsupported
activities and failed recovery remain paused and require native controls. Ordinary
key/action/Resume stays forbidden at recovery boundaries; never auto-confirm.
A recovery timeout preserves `control_pending`, its durable admission and unknown
history separately from the original gameplay request. Passive status cannot clear
the live slot. After the fixed two-second native deadline, an explicit fresh
observe can reconcile transport capacity; it cannot establish the old outcome.
Any next recovery must be a deliberate new request against current evidence.

## Native acceptance lane

Required after relevant native/input/renderer/protocol/source-pin/compiler changes,
and before new native support claims. Complete relevant probes on an isolated
project profile, windowed, without hidden information or edited saves:

1. Commit the source checkpoint under [S-DELIVERY](engineering.md#s-delivery-reproducible-and-isolated-delivery), then build the pinned source using setup; record compiler, inputs and binary hash.
2. Inspect actual native and spectator frames, including menus and popup text.
3. Exercise observation, bounded input, stale authority, pause and native takeover.
4. Exercise the changed behavior plus timeout/reconciliation and restart as relevant.
5. Use normal save/load if persistence or session identity is affected.
6. Record each outcome, unknown/failure and scope in a dated report and small manifest.

The [MVP report](acceptance/2026-10-17-mvp.md) is an example and historical evidence,
not an executable current pass. Portable tests never substitute for this lane.
A new automated native replay/probe runner remains a documented coverage gap.

## Evidence retention and cleanup

Track small reports/manifests, source pins and checks in Git. Keep user saves,
large media, journals, credentials and downloads out of Git. Use Git commit/tree,
diff and PR for source identity. A manifest records external artifacts' relative
paths, byte counts, hashes, source/candidate and limitations. Snapshot
journals before indexing them: a live journal can append even during normal shutdown.
Keep the full live journal, label the snapshot/cutoff, and verify its bytes/hash; do
not truncate a journal or overwrite a historical hash to hide later events. A hash
identifies bytes; it does not prove the depicted behavior without inspection.

Retain curated acceptance artifacts and failure evidence until superseded by
reviewed equivalent evidence or explicitly selected for removal; if removed,
record availability as removed in the evidence index. Keep unresolved-incident
journals until resolved. Routine unreferenced journals/frames can be pruned after
30 days, only with sessions stopped and after checking references/ownership.
This initial policy is manual; no scheduled deletion is installed. Native frame
rotation within a live process remains the game's existing bounded behavior.

Never delete saves as routine cleanup. Preserve manifests before removing owned
build directories/downloads. Identify the exact path from the build manifest and
verify its checkout ownership marker; never use broad /tmp or global-cache cleanup.
For a lost temporary build, re-extract using setup. For an unreadable archive,
remove only the named corrupt cache entry after preserving diagnostics.

Fresh source checkouts contain acceptance metadata but not local demo media.
Maintainers must distinguish unavailable evidence from a newly failed probe.

## Coordinated migration

Follow [S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration)
for every contract change. Stop the controller and affected writers, save/quit CDDA
normally if running, and confirm the owned processes stopped. Record the affected
formats and exact code versions; preserve original files and hashes before conversion.
Migrate the entire producer/consumer/tool/configuration set and its current docs.

Validate converted data against the new contract before replacing active files.
Unsupported bridge records block startup; do not delete admissions or infer a
successful action to make startup pass. Reconcile incident evidence offline while
keeping unknown outcomes unknown. If meaningful conversion is impossible, retain
an incident archive and document the explicit transition to a fresh bridge with
unresolved work still tracked. No replay or save editing is permitted. Historical
reports and journals stay immutable; they need no runtime reader.

Build manifests require `schema_version: 1`; evidence stores require store version 3.
Never just relabel an unknown file. A reviewed one-time build-manifest migration
must first verify workspace ownership, pinned source/headers and binary hashes,
then record before/after hashes. Alternatively preserve the old manifest/workspace
and use a fresh extraction. Permanent setup/startup paths only read current formats.
Remove temporary converters after recording their operation. Roll back only as a
coordinated system with a validated data transition, never by enabling a fallback.

For the wire-v4 cutover, archive the stopped bridge with original hashes under
`.runtime/incidents/` and start a fresh bridge. Do not relabel old requests. Carry
unresolved identities as verified `incident/1` references in
`historical-incidents.json`; startup validates referenced bytes without parsing
old protocol records. These remain visible historical unknowns and grant no
execution permission. Evidence store format 3 accepts only current-v4 observations;
archive earlier stores and start new task stores, preserving original metadata.

## Passive skill acceptance

The movement skill is a library, not a new CLI command or live player. A manual
acceptance caller binds TaskSpec and retained start evidence, requests one proposal,
reserves an after-frame, dispatches once through the existing controller, retains
the exact logical/native identity mapping, and settles once. Follow the
[skill contract](protocol.md#passive-bounded-movement-skills); do not pass a controller
walk loop as a primitive or automatically Observe/retry an unknown input.

The [round 009 report](acceptance/2026-10-17-bounded-skills.md) separates actual native
frames from injected evidence faults. Preserve raw unsupported receipts outside
the task store. A rendering failure cannot be repaired by substituting a later
frame. Save normally and stop only owned processes after acceptance.

## Designated campaign operator

Use the [current actor contract](protocol.md#designated-campaign-operator). One
explicitly designated general-purpose player makes mission decisions; explorers
and reviewers are read-only. Its frozen brief identifies source/native, prospective
limits/reserve, allowed typed requests and memory/output paths. Verify actual-player
passive access before admission. The lead owns the runtime and acceptance, without
ordinary gameplay rescue in the deciding attempt.

Before lead inspection or player replacement: request Pause, finish every tool
handle, retain the checkpoint, verify no queued/scheduled action and obtain explicit
quiescence. Cached status alone cannot prove the agent's queue is empty. User
Pause/native takeover prevents automatic continuation. The registered one-use
handoff and real fresh context must preserve original costs and retrieve retained
memory; their source adapters compose, while actual fresh-context/native acceptance
remains required. Do not substitute raw inputs or lead-written
reconstruction to make acceptance pass. Historical operator reports remain evidence,
not standing admissions or a second runtime mode.

## Typed mission requests and the player

The current service has one mission runtime and `/api/mission`. The old waypoint
Start/Continue/Abandon/planner inbox and `gameplay-*` CLI are removed, with no alias.
The [mission contract](protocol.md#integrated-mission-lifecycle) and strict source
schema own the supported records; the [design](design/player-owned-mission.md)
separates implemented components from remaining independent-play acceptance.

1. Freeze the exact reviewed candidate, finite objective/scenario/limits/reserve,
   actor, native build and permission preflight before gameplay. The initial
   admission is not authority to adopt an unrelated open character.
2. Put one current mission/6 record in project `.runtime/mission-requests/record.json`.
   Use `.venv/bin/python -m harness mission-request --request
   .runtime/mission-requests/record.json` from this trusted checkout. The CLI accepts
   a regular bounded JSON file directly in that directory, validates it and sends
   one authenticated request. It does not run code or create an arbitrary process.
3. Start is source-free; explicit Observe is passive. Registered owned lifecycle must establish
   world/character identity and fresh input authority. Source lifecycle composition
   has synthetic coverage; native character/mission acceptance remains required.
   Do not substitute raw keys/Resume or a trusted unit fixture.
4. Read the result by its exact operation ID. Accepted only acknowledges admission;
   wait for the settled immutable result and inspect the frame/effect. A lost response
   is not nondelivery. Never change a request body under an existing ID or blindly
   replay an uncertain input. Busy admission is a visible rejection, not a queued
   future action.
5. The player requests bounded context, reads needed retained sources, records
   fallible claims/corrections/Work and chooses semantic goals. The observer's last
   context packet is historical, query-specific and possibly incomplete. Its labels
   are as-of that packet; use a new explicit query to judge current knowledge.
6. Owned menus support bounded focusing, literal text and direction/confirmation
   handling. Dismissal uses one registered QUIT or editor TEXT.QUIT, returns partial
   for effect verification and never automatically answers a new prompt. Original
   root/child limits and unknowns stay recorded. Untouched-menu exit uses its owned
   lifecycle root and an explicit interpreted confirmation child. It is not a
   character save/exit path. Item/activity, creation/save/reload and handoff adapters
   compose in source; actual native outcomes and independent-player qualification
   remain required.
7. Pause prevents further admission, without undoing an input or native activity.
   Honor user Pause/takeover; do not auto-Resume or restore a phase from disk. A
   stopped deciding attempt remains stopped. Normal cleanup, actual fresh-context
   replacement and full mission acceptance are separately required.

The lead owns source/integration/admission and verification. The deciding player
owns ordinary tactics and supported lifecycle; source faults or unsupported required
capabilities stop the attempt with evidence instead of inviting engineering rescue.
Role assignment is procedural, not filesystem isolation. Optional curation or
additional model tiers do not gate this functional path. No paid API is implied.

The [stopped functional continuation](acceptance/2026-10-18-seven-day-continuation-stop.md)
and [ordinary menu repair](acceptance/2026-10-18-ordinary-menus.md) retain historical
coverage and failures. Their old CLI/recorders and expired admissions cannot authorize
current play. #156 freezes the actual candidate; #157 owns deciding mission evidence.

---
owner: maintainer
review_trigger: Launch, control, recovery, recording or storage changes
status: active
---

# Operate, recover and retain evidence

Supported scope: one prepared local macOS game.
For fresh installation use [setup](setup.md); use [overview](overview.md) for limits.

## When a run owns input

The viewer identifies an active run owner and disables ordinary inputs and Resume.
Observe and Pause stay available. Use Pause to take over, inspect a current frame,
and explicitly Resume before manual input. A released or revoked run is not
restored by Resume. Recording goal text never starts or replaces a task.
The explicit waypoint task controls acquire a run lease through the runtime;
the planning-only player never receives it. Restart begins paused without ownership.
If a result is unknown, preserve it and reconcile under the procedures below;
acquiring new ownership does not prove the old task succeeded.

## Start and observe

First inspect existing terminals/processes to avoid starting a second game or
controller. A native app lookup by name may launch a second copy when the game
was started directly by its wrapper; do not use lookup as a process-existence check.
Use the existing spectator to inspect native frames when a tool cannot bind the
already-running native window.
Do not kill an unrelated service to free a port. From this checkout,
use an available loopback port and launch only the prepared project bundle:

```sh
.venv/bin/python -m harness serve --port 8766
open .runtime/Cataclysm.app
```

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
viewer goal field records an objective; it does not start another agent.
A registered action can be rejected if it has no usable single-key binding. A
walk may report `stopped` after all requested steps completed; inspect `steps`
and the frame before deciding again. See the [protocol](protocol.md).

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
The [direction-menu acceptance](acceptance/2026-10-18-native-direction-menu.md)
records actual rebuilt-engine Escape, adjacent selection and empty-current-tile
behavior without user keys. The reuse-first desktop-tool preflight failed before
admission; this narrow support does not establish general native recovery.

For service restart: stop that service normally, start one controller, observe
and reconcile, then resume. For a game crash/restart: preserve diagnostics, follow
the bundle-based [start procedure](#start-and-observe), use normal CDDA load UI,
and acquire new session authority.
Old-session commands must not be reused, including after normal save/reload in the
same process. Native-v3 rejects older and mixed components; restart a
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

Build manifests require `schema_version: 1`; evidence stores require store version 2.
Never just relabel an unknown file. A reviewed one-time build-manifest migration
must first verify workspace ownership, pinned source/headers and binary hashes,
then record before/after hashes. Alternatively preserve the old manifest/workspace
and use a fresh extraction. Permanent setup/startup paths only read current formats.
Remove temporary converters after recording their operation. Roll back only as a
coordinated system with a validated data transition, never by enabling a fallback.

For the wire-v3 cutover, archive the stopped bridge with original hashes under
`.runtime/incidents/` and start a fresh bridge. Do not relabel old requests. Carry
unresolved identities as verified `incident/1` references in
`historical-incidents.json`; startup validates referenced bytes without parsing
old protocol records. These remain visible historical unknowns and grant no
execution permission. Evidence store format 2 accepts only current-v3 observations;
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

## Explicit waypoint tasks and the player

The service supports one bounded waypoint-and-return task. Start from a fresh
normal-play observation after explicit transport Resume. Native input and saved
goal text do not start a task. In the spectator, choose a cardinal direction and
1–4 tiles, then Start task. The origin/target are constructed from current visible
state. A direction is a bounded request, not a guarantee that every route tile is
safe or known. Each step must pass the current guard.

The equivalent project-local CLI is `.venv/bin/python -m harness gameplay-start
east --distance 1 --expect SESSION:REV`, using the actual observation that informed
the decision. `gameplay-request` reads the pending task/evidence/skill/binding packet.
The dedicated player sub-agent reads that packet and retained frame, then submits
one validated candidate file with `gameplay-plan REQUEST_ID --candidate PATH`.
Only the player proposes the candidate; an acceptance script must not manufacture
plans and label them model decisions. Candidate reasons are concise public
justifications, not a private reasoning transcript. Start the player before task
admission so the 30-second call ceiling is usable; task wall time remains 120 seconds
including planning and Pause. No response means stop, not automatic replanning.

The lead supervises and owns the game/service; the player must not start/continue
runs, resume, send raw inputs, edit source/saves, or launch another process. Both
use one external planning contract. Sub-agent role instructions do not remove its
inherited tool permissions. Keep the planning brief narrow and retain requests,
responses, real receipts and frames. Codex usage and model identity are unmeasured
unless independently recorded; the harness makes no paid model API calls.

After a slow response, the service reobserves and explicitly proves the unchanged
visible scene before admitting input. Changed evidence stops; it never rewrites the
candidate binding. The spectator shows planning, current stage, verified progress,
next check and failure/unknown reasons. Read evidence details when judging progress;
transport delivery alone is not task completion. Status polling does not renew
freshness or a planner deadline.

Pause always takes control immediately, even while planning or waiting for native
input. It cannot undo an already committed action. Reconcile with Observe and
explicitly Resume transport, then use Continue task (or `gameplay-continue RUN_ID
--epoch N --expect SESSION:REV`) only if current evidence matches the retained
checkpoint and no effect is unresolved. Original history and all budgets remain;
already verified legs are not replayed. Unknown effects prohibit continuation.

Completion releases ownership and pauses transport. A stopped/completed task stays
visible until Abandon task (`gameplay-abandon RUN_ID --epoch N`); await worker exit
before starting another. Abandonment preserves evidence and does not erase unknown
native effects. Service restart does not restore an active task. Stop the dedicated
player at the end of the session, then save/quit normally and close only owned
processes under the existing cleanup procedure.

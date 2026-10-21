---
owner: maintainer
review_trigger: Native bridge, controller, input, observation or skill change
status: active
---

# Bridge and guarded-play contract

Protocol version: 4.

This is the detailed current contract supporting [architecture](architecture.md).
Authority rules are [S-PROTOCOL](engineering.md#s-protocol-command-and-observation-authority).
Portable checks do not prove native engine behavior.

Unsupported versions and alternate response shapes are rejected. Startup validates
stored admissions, claimed requests and any response before restoring uncertainty;
it never converts old records. A dispatched response without its current-format
input identity blocks startup instead of fabricating a synthetic request. An offline
migration must preserve uncertainty and cannot grant authority or replay inputs.
See [coordinated migration](runbook.md#coordinated-migration).

## Controller run ownership

The in-process controller API exposes `acquire_mission(mission_id, epoch,
actor_id, *, operation, expected_session, expected_revision, expected_boundary_id,
replace=None)`,
`execute_mission(lease, *, kind, value, expected_session, expected_revision,
expected_boundary_id, logical_action_id, deadline_monotonic, timeout=None,
expected_image_sha256=None, preflight=None)` and
`release_mission(lease)`. Operation is navigate, interaction or lifecycle.
A frozen MissionLease belongs to one controller; only the exact returned Python
object authorizes input. Status `mission_lease` contains descriptive mission/actor/
epoch/session, host pause generation, native takeover generation and operation;
JSON cannot reconstruct the capability. Navigation permits guarded cardinal
movement only at normal play. Interaction/lifecycle can also use supported menus;
activity/debug/unsupported boundaries never admit ordinary keys.

Acquisition is explicit, nonblocking and has one winner. It requires no active or
queued ordinary/control writer, live lease, pending effect or native inbox, plus
reconciled, unpaused, fresh successful operation-eligible evidence matching the
supplied session/revision/boundary. It rotates native authority and admission generation without
observing, resuming or dispatching. Historical unknowns remain historical unknowns;
new ownership cannot establish the outcome or continuation of an older task.
Deliberate operation rotation supplies the exact live capability as `replace`.
It preserves mission/epoch/actor/session and requires the same empty writer slots
and unchanged Pause/takeover state. Rotation revokes the old capability and advances
host generation under the admission locks, without Pause or an input gap for an
external writer. A serialized lease description cannot request replacement.

Ordinary external key/action/walk/resume reject while leased. Existing HTTP/CLI
input reaches this same controller gate; it cannot supply or obtain a capability.
At the controller layer Observe/status, record-only goal and Pause remain
available. HTTP further routes nonterminal mission Observe through typed ingress
and blocks raw input/recovery. The viewer displays mission ownership; a model call
never holds controller locks. Only registered mission operations can request a
lease; service startup, admission and transport Resume never establish identity.

A leased call submits one registered action or permitted key, using native-v4
observation and input checks. Intended boundary and human takeover generation are
bound in native action/key/resume requests and checked at native commit. The original command admission generation and exact live lease
are checked around queueing/preflight and immediately before atomic publication.
Every walk step uses its original entry generation. Pre-takeover or pre-acquisition
queued inputs cannot become current merely by waiting. No stale expected revision
is silently refreshed.

Pause and release revoke before returning; release requires the current capability
and also pauses. Recovery, native takeover/session change, a paused native
observation, transport failure and shutdown invalidate ownership. Resume does not
restore a lease. Startup restores no task or capability. Native token validation
remains the final input commit gate; an already committed action cannot be undone.
The controller serializes durable publication, revocation and some journal writes
under its data lock. A filesystem stall in that critical section can delay Pause;
there is no hard response-time guarantee under disk failure. Runtime memory/model
work must add no lock that delays revocation, and native activity cancellation
remains separate from revoking further harness inputs.
`execute_mission` returns an envelope containing the logical action ID, exact native
`request` or null, `result`, `published`, original terminal
`received_monotonic` or null, and nullable `preflight`. The latter contains the
copied final Observe, its original `received_monotonic`, and
`expected_image_sha256` or null. Preflight Observe is not an action receipt. The
absolute monotonic intent/task deadline is checked after queueing/preflight and
under the publication lock; it bounds both exchanges and the native deadline.
`observation_snapshot()` returns a copied current observation and original first
receipt clock. Reading a snapshot does not renew its freshness.
Passive captures may change transport id, timestamp and frame filename without
changing native state. Live-versus-retained comparison excludes only those three
fields; it retains status/error/frame validity and complete semantic/Pause/takeover
state. This grants no freshness or image equivalence. Immutable ACK/UUID and
retained preflight correlation remain exact; image-informed inputs retain their
PNG and native commit checks. Recovery hashes the sampled live PNG outside the
Pause lock and fences its frame identity. Interruption answers still require their
exact native frame, so an intervening capture can stop before publication.

The trusted Python-only `preflight` callback receives that copied Observe and
actual receipt after boundary/lease/image checks, inside the command lock but
outside the data lock. Runtime may retain the exact source, reserve after-frame
capacity and commit a durable intent before publication. The controller rechecks
owner, Pause, recovery, boundary, freshness and the original deadline afterward.
An ordinary callback exception stops before input publication and freezes/revokes
the owner; secondary persistence failures remain explicit diagnostics. A crash is
not converted into proof of nondelivery. Callback and expected-image arguments
are never accepted from public command JSON.


`resume_mission` accepts the exact recorded controller boot, host operator-Pause
counter, general authority generation and native session,
revision, boundary, takeover count and diagnostic origin for a runtime-admitted
transition. It rechecks after queueing/observation; a newer Pause/takeover wins.
It does not establish an admitted phase itself. Public command JSON cannot call
this API, and an old lease cannot Resume. Runtime integration remains separately
tracked; these controller capabilities alone do not make a player autonomous.

## Integrated mission lifecycle

The project-local structured player adapter describes current semantic arguments
from these same schemas and submits to the same authenticated ingress. It supplies
common headers from an explicitly selected returned snapshot, derives ordinary
bindings with the pure producer and retains the exact stable request before the
first POST. Repeating a staged identity collects only its original result; a lost
reply never permits another action POST. Bounded process-local handles grant no
authority and are not persisted history. `enactive_start` belongs to the lead's
frozen admission; player skill, memory and lifecycle choices remain explicit.

Authenticated `GET /api/mission/source?mission_id=ID&source_id=ID` and
`GET /api/mission/frame` with the same exact query expose one indexed original
archive entry/PNG. Both require the local token, exact query keys and the atomically
published mission/store binding. Metadata includes reference, observation,
retained/disputed disposition and `grants_authority:false`; image reads verify the
original bounded PNG hash. They use neither an arbitrary path nor a newer bridge
frame and do not renew evidence clocks, Observe or mutate a lease. Missing/changed
bytes fail. Runtime input validation still owns sticky invalidation and freshness.
Storage replacement retires the presentation binding before closing the old store.
The [adapter brief](changes/051-structured-player-tools.md) separates source/SDK,
actual host zero-review and native acceptance.

The service constructs one [MissionRuntime](../harness/mission_runtime.py), with
one bounded writer, one queue slot and no automatic admission, launch or Resume.
The old waypoint runtime and its live API/CLI are removed. Passive movement,
planner and supervisor components below remain source/study tools, not another
execution ingress. The [mission design](design/player-owned-mission.md) owns the
chosen records, lifecycle requirements and separate native acceptance.

Authenticated `POST /api/mission` accepts one strict mission/7 record, at most65536
UTF-8 bytes. It reuses host/origin/token and finite/duplicate-key JSON validation;
operator command/recovery bodies keep4096-byte limits. Required fields and closed
variants live in [mission_contracts.py](../harness/gameplay/mission_contracts.py),
not a second HTTP schema. Unsupported versions and `/api/gameplay` reject, without
conversion. Admission and original deadlines/costs persist in the ledger; parsed
JSON and status contain no executable lease.

Start records source-free admission and sends no native request; explicit Observe
remains passive. Even already-unpaused normal play does not prove the named world/character, receive a lease or seed the mission's game-time
anchor. Registered creation/load must establish those facts after owned launch.
Registered creation/save/load and provisional character inspection now compose in
source tests through the real controller, ledger and evidence archive. Quiescent
successor handoff and deliberately charged readmission also compose in source.
Selected item/inspection roots, owned quantity editing and one-observation activity
polls and registered activity interruption/answer/resumption now compose in source.
Selected delivery reconciliation and separate normal-play readmission now compose
in source; normal finish has source coverage. Unsupported semantic uncertainty
remains stopped rather than being passed through unknown-delivery reconciliation.
[Native007](acceptance/2026-10-20-native-lifecycle-qualified.md) qualified ordinary
creation/identity, counted drop/pickup, a known two-step return, bounded native
wait/poll, normal save/new-child exact reload and normal final stopped Finish.
The independent mission remains unqualified. Native006 retains its actual failure
and exceptional second-child cleanup; later success does not rewrite it.
Neither synthetic UI tests nor tests assuming identity accept an independent mission. Observe likewise cannot adopt
an unexplained normal session. Reopening restores neither phase nor input authority.
The lifecycle Resume checkpoint is refreshed once at entry inside the registered operation
before proposal/publication. The existing guarded Observe must preserve exact
native state and PNG bytes, original actor/operator/takeover and root/child/mission
deadlines. Its journal links old and fresh source IDs without constructing a
lease-bound SourceBinding before a lease exists. It sends no input or grants
readmission by itself. Explicit creation-stage commit, normal save and identity
inspection use the same guarded refresh with typed exact-PNG SourceRevalidation.
Ordinary semantic controls and navigation likewise capture/revalidate once at entry,
even if the selected source is still fresh. Interpreted controls require exact PNG
equivalence; native-row/navigation decisions retain native-state equivalence.
A replacement that expires before final dispatch still fails. This bounded Observe
cost does not renew requests, phase limits, authority or the freshness threshold.
[Entry-refresh rationale](changes/053-operation-entry-refresh.md).
Save refresh precedes operation rotation and preserves its original normal-game
time anchor. Changed state, Pause or expiry still stops input.
An atomic controller snapshot keeps a frame's first-seen clock; a command reader
can receive the same frame's matching ACK later. Terminal delivery checks validate
both clocks independently, without imposing their ordering or renewing either.
The original terminal clock remains fresh, after its preflight, and bound to the
exact native UUID/state; source/PNG/authority checks remain. Snapshot mismatch
records its actual state and valid clock for diagnosis before stopping. These
historical receipts never restore a revoked phase or input consent.
The harness-enabled SDL ImGui context disables only input-text cursor blinking
through its existing library option; exact encoded PNG equivalence is unchanged.
There is no image masking or tolerance for changed content. Other animations can
still invalidate an old interpreted decision. General setup cancellation after
other setup inputs remains unsupported; only the proven Resume-only main-menu
case below has a narrow normal cleanup path.
Interpreted tab focus excludes WORLDGEN_CONFIRM_DIALOG. NEW_CHAR_DESCRIPTION may
return through PREV_TAB, but NEXT_TAB starts character completion and requires an
explicit lifecycle stage commit; a focused menu outcome cannot authorize it.

Registered lifecycle launch is a source-free root: null phase/Work/native binding,
empty source/identity IDs and exact admitted names. It invokes only the fixed
prepared NativeProcess with its admitted binary hash. Original root/mission wall
and cleanup limits include process validation, exec, command queueing and native
readiness. It retains child custody after cancellation/timeout; a second launch
or admission replacement cannot silently replace it. A fresh paused untouched
MAIN_MENU, empty error, valid rendered frame and unchanged actor/epoch/controller/
operator counter are required for a readiness receipt. It remains passive: no
Resume, lease, normal facts, identity or game-time anchor. Portable fake-process
tests are not actual native launch acceptance.

Cached process facts are last samples, not a liveness guarantee. Shutdown journals
any owned child without signals; reopening restores no process handle. Only a
validated committed OwnedNormalExit resolves that launch's historical custody.
Otherwise attempted/uncertain launches remain unavailable, with no PID adoption.
Process absence or exit code alone cannot prove a normal save/exit.

Registered `exit` covers the same owned untouched MAIN_MENU, a verified Resume-only
pre-character menu, or a menu reached by this child's validated SavedCheckpoint.
Resume-only eligibility requires exactly one correlated returned create/load Resume,
no other setup input, unknown, transition candidate or normal-play evidence. The
fresh internally paused menu must retain the immutable launch pixels and expected
Resume revision/control transition under the original operator/takeover mark.
Read-only Observe can adopt that private cleanup checkpoint; it grants no input.
Ledger write/reopen/orphan checks audit the original Resume mapping/source IDs;
runtime and EvidenceStore own PNG and live-authority checks. An earlier exit must
have no inputs or its fully settled verified No; pending/unknown exit inputs cannot
be skipped by a new root. This does not handle arbitrary setup rollback or restore
consent after user Pause.

While that Resume-only create/load phase is still live at MAIN_MENU, a new
source-bound `exit` root may explicitly request its abort. It audits the original
single Resume, actor/operator/custody, no normal segment/other input/candidate or
pending slot, then compares a new native capture with the exact original pixels
and expected resumed state. It revokes setup through internal recovery without
sending input or changing the launch checkpoint. The plain partial result reports
`cleanup_requested`, not an exit proof or a phase receipt. The original request
epoch remains historical; the ledger's pause advances its current epoch. Separate
Observe must establish the fresh internally paused Resume-only menu, followed by
a new finite normal-exit root. Neither step restores the old setup phase, renews
mission ceilings nor overrides a concurrent user Pause/takeover. Other setup
screens/inputs, unknown Resume and historical reopened evidence cannot use this
abort path. The saved branch requires the exact final
normal endpoint and its original first menu source, even after later observations.
It retains the launch's original operator mark.

Reload staging follows actual native transitions: a returned MAIN_MENU world
confirmation entering UILIST arms the private character-selection stage; return
to MAIN_MENU retires that stage. Before a load confirmation is dispatched, the
rendered UILIST must have one enabled admitted-character row and that exact row
must be selected. No literal `Load Game` label or alternate label reader arms the
stage. Unknown delivery retains its original UUID/reservation; diagnostic Observe,
same-root transition reconciliation, separate identity-only Resume and visible
identity Claims/adoption remain required. The row check establishes selection
only; world identity still needs its source-backed interpretation.
A source-bound root charges distinct Resume and QUIT primitives, then awaits an
explicit interpreted Really quit? Yes/No child. Exact-PNG refreshes preserve
checkpoint provenance; root/child ceilings and original deadlines never renew.
The selected confirmation refreshes once at operation entry before proposal. Its typed
exact-PNG SourceRevalidation must link the immutable interpreted source to the
actual dispatched before-source. Normal result and orphan-effect validation enforce
that relation at write and reopen; native-state equivalence alone is insufficient.
This branch uses ordinary budgets and preserves the cleanup reserve. A verified
No returns the owned paused main menu without claiming exit. Only published Yes,
unchanged controller/native authority, the retained child's normal code0 exit,
matching terminal input/effect and narrow controller retirement produce a closed
OwnedNormalExit. The original ACK can remain unknown; its cost/history/admission
file stay retained. Retirement clears only matching expired in-memory pending
state after durable recording, stays paused/frozen and sends no input or signals.
Lifecycle PhaseReceipt/exit proof are historical data, never restored permissions.
Any unexpected normal frame remains diagnostic: registered identity/adoption is
required before time cost, maps, native memory facts or ordinary dispatch, including
after reopening. The saved-exit branch passed scoped
[Native007 qualification](acceptance/2026-10-20-native-lifecycle-qualified.md);
independent normal-game mission acceptance remains separate.

Registered create/load starts only from the retained launch's paused main menu.
Explicit stage commits request world FINALIZE or final character NEXT_TAB; the
player separately interprets each confirmation, including discarded spare points.
Save starts only from adopted normal play and its own Save and quit? confirmation.
Each action uses the ordinary charged dispatch and original root/child ceilings.
A confirmation's `question` contains only the exact base question; an adjacent
case-sensitivity legend is not part of that field. Local wrong-kind/missing or
wrong-question interpretation returns plain blocked before refresh, rotation or
input. It consumes a semantic request but not a primitive, retains the original
phase/lease/deadlines and creates no new authority. Repeating the same request ID
returns its immutable blocked result. Re-read the original phase and submit a new
corrected request; its full freshness, exact-PNG, actor, Pause and budget checks
still apply. Points-stage changes install only after full validation. This narrow
request rejection does not soften wrong sources, changed pixels, expiry, user
Pause or unknown delivery, and makes no claim about the current native scene.
A changed-session terminal ACK remains unknown. Diagnostic Observe retains the
actual after-frame against that dispatch's exact capacity reservation; a separate
same-root current-epoch request records LifecycleTransition and reconciles effect
without relabeling the ACK. Only then may explicit provisional readmission inspect
PLAYER_INFO; only QUIT may return from that screen. Inventory or movement cannot
use provisional normal evidence.

NormalSessionAdoption requires directly supported, undisputed admitted world and
character Claims, the exact identity inspection, owned transition and current
normal checkpoint. The [historical reader](../harness/gameplay/lifecycle.py) validates
all retained normal sessions, corrections, canonical order and exact saved endpoint
links before establishing time, coordinate epoch, native facts or a normal binding.
It grants no authority and may quarantine corrupt sources through EvidenceStore.
Save/reload preserves the initial time anchor, cumulative costs and unknowns;
new coordinates never inherit old relative vectors. A rejected candidate adoption
can be explicitly corrected within its original phase/deadline. Reopen verifies
history but reconstructs no process handle, phase, lineage, lease or queued input.
Native007 qualified the selected actual creation/save/load path. Independent
mission acceptance and actual fresh-context memory use remain pending.
[Native008](acceptance/2026-10-20-confirmation-correction.md) additionally qualified
world and Save local-question rejection followed by new exact guarded correction,
identity/adoption and normal save/exit/stopped Finish. Original unknown delivery
and the failed independent001 remain retained; no independent objective is accepted.

### Skill request binding errors

Construct `expected_session`, `expected_revision` and `expected_boundary_id`
programmatically from the single chosen retained observation associated with the
cited source. Use existing JSON tooling; do not copy opaque fields independently
or carry an earlier boundary across a focus change. A source reference alone does
not expose every native field: read its declared observation metadata and verify
the pair. A draft, cached status or historical source grants no input authority.

The canonical pure producer is `harness.gameplay.mission_requests.compose_request`.
Supply a mission status snapshot (all three phase summaries, including nulls),
one explicitly selected retained archive entry (`reference` and `observation`),
semantic skill/lifecycle intent, new request ID, finite limits and an explicit
`new_root`, `prompt`, `lifecycle` or `activity` scope. It derives the source/triple,
mission/epoch and selected phase's direct origin together; opaque headers and
`perception.source_id` in intent reject locally. The existing validator owns
wire shape and bounds; `canonical` remains the serializer. It performs no I/O,
source selection, refresh, clock checks, dispatch or authority grant.

Additional informing source IDs are explicit bounded support: a two-observation
transition selects its latest binding bundle and cites its first observation as
support. A phase scope requires that exact summary/checkpoint, without falling
back to another phase or null root. Prompt supports only menu/edit/inspect/item/
activity children; activity scope supports only activity. Lifecycle children keep
their direct create/save/load root, including provisional identity inspection;
exit confirmation is a lifecycle-scoped menu child. No unrelated Work attaches
to lifecycle skill children. These composition checks do not duplicate live guards.

Source-free launch is an explicit new root with no bundle/support. Explicit new-root
exit alongside create/load only expresses the existing narrow setup-abort intent;
the receiver determines eligibility. Retained final-source Finish and frameless
activity checkpoints do not require `current_source`. The initial activity poll
uses its public prompt scope; after interrupt, select its public activity scope.
Memory, handoff, claim, recovery readmission and post-reconciliation navigation
continuation retain their specialized typed records. The producer adds no wire,
persisted format, alternate executor or compatibility path. Review it with contract
or phase-summary changes; real-component tests detect drift. Replace it if maintained
upstream composition tooling fills this concrete gap at lower maintenance cost.

The writer checks an internally inconsistent expected triple before adapter
mutation or refresh only when the cited current source is exact and available,
and any explicit perception names that same source. Existing read-only ownership,
authority, original budget and integrity fences must still pass. Then it records
plain blocked without Observe, rotation, reservation or input, retaining the
original phase/checkpoint, lease/epoch and deadlines. It never substitutes fields
or certifies freshness. Same-ID results are immutable; a new corrected request
traverses every normal guard. Request counts and elapsed time remain spent.

Actual Pause/takeover, unsettled delivery, wrong ownership, missing/disputed source
or exhausted budgets retain their existing stops. Frameless activity states that
cannot establish exact retained/live equivalence use their specialized handling;
this is not a generic EvidenceError exemption or menu recovery route. Real
native correction qualification remains separate from portable coverage.
[Deciding002](acceptance/2026-10-20-independent-mission-second-attempt.md) retains
the stale-boundary failure that motivated this change; it cannot resume.
[Native009](acceptance/2026-10-20-request-construction-qualification.md) separately
failed before the declared probe after omitting the direct identity root. It cannot
resume either; pure producer tests do not replace a new finite native qualification.

Prompt-opening inspection/item/activity roots require room for opening and return:
limits below two primitives return a correctable zero-input refusal, without
creating a phase or renewing any allowance. Allocate the finite whole-phase cap
for all controls, verification and return (normally up to32); it is a ceiling,
not an upfront charge. Existing lifecycle roots separately include Resume and all
children. This minimum is not a guarantee that a larger task fits its chosen cap.

Semantic menu dismissal selects exactly one action by captured context:
`STRING_INPUT` → `TEXT.QUIT`, `UILIST` → `UILIST.QUIT`,
`WORLDGEN_CONFIRM_DIALOG` → `WORLDGEN_CONFIRM.QUIT`, otherwise the existing `QUIT`.
That action must actually be registered in the selected evidence; missing actions
block with zero proposals, without trying a different alias, NO, confirmation or
raw key. A delivered dismissal returns partial for verification and never answers
a newly opened question. Upstream UILIST cancellation is conditional; category
admission alone does not establish that cancellation is enabled. First worldgen
cancel support does not implement a general setup-abort lifecycle.
[Native010](acceptance/2026-10-20-menu-dismissal-qualification.md) exercised the
narrow binding correction, then failed normal ending on the old generic-QUIT
mapping. The translation repair still needs new finite native dismissal/ending
qualification; the failed attempt cannot resume.

MissionLimits permits at most 691200 game-seconds (eight days); its default remains
43200 seconds. Each finite admission must budget normal ending work before its
selected cap. Every input lane checks known canonical game cost before publication,
including lifecycle and readmission. Reaching or exceeding the cap prevents input
and revokes authority after settlement, with no cleanup exception. Startup has no
adopted game clock and keeps its existing independent guards. Read-only Observe
and user Pause do not dispatch inputs. Raising the software maximum extends no
existing admission and establishes no native survival outcome.

`lifecycle(operation=finish)` is the sole normal finish route. Stop carries only
its Pause reason; former Stop `finish` fields and mission/2, mission/3, mission/4,
mission/5 or mission/6 records reject. The
current mission/7 contract migrates CLI, viewer, requests, results and fixtures
without an alias or automatic old-admission import. Campaign memory advances to
campaign-memory/3 and SQLite to ledger9. Native wire4, gameplay/2 and archive3
remain unchanged. Prior accepted reports and raw older mission/memory/ledger
artifacts remain historical evidence, not current request inputs. Closed failed
missions stay closed; a new admission uses a new mission directory, with no
automatic old-state import or restored authority.

Finish sends no Observe, Resume or game input. It requires empty writer/controller/
native slots, no live phase or unresolved effect, every owned launch's unique
committed normal exit, and its exact retained final source. Source age alone does
not invalidate this historical proof; missing/disputed bytes do. No objective Work
means stopped cleanup. Player-reported completion requires the exact latest Work
event matching the admission objective, coherent observed progress, retained
sources and the last adopted coordinate scope. That interpretation is separate
from independent campaign acceptance. Historical finish validation uses Work as of
that report; a later legitimate update cannot rewrite its history.

The immutable NormalFinish report precedes terminal mission persistence. The
terminal transaction checks the exact epoch, original operation/mission deadline
and matching report; the final cancellation/operator fence gives an earlier Pause
precedence. Cancellation, expiry or crash between those writes preserves the
report without automatic terminal replay. Reopen remains paused unless terminal
persistence had actually completed. Successful terminal persistence releases the
exited child handle/owner while retaining sampled facts and receipts, permitting
a new explicit mission. The observer distinguishes reported completion, cleanup,
current mission phase and independent acceptance. Synthetic tests do not qualify
native final shutdown or the independent mission.

### Selected item, inspection and activity composition

Mission/7 retains explicit item units (`items` or `charges`) and root/select/commit
steps. The pure [item policy](../harness/gameplay/interactions.py) checks exact
represented target, native row contradictions, known availability and chosen
count. A focus batch sends at most eight observed arrows and never confirms.
Multi-selection opens the native count field with one `MARK_WITH_COUNT`; only its
exact returned transition gives that private item phase quantity-editor ownership.
The pinned engine uses the same string-popup implementation for count and filter,
so interpreting the field as a count is insufficient. Its edit must use the
immutable root quantity; filter relabeling and ordinary menu confirmation cannot
bypass this path. Literal editing and fresh whole-value commit are separate.
Returning to the selector still requires fresh interpreted count/unit and complete
selection coverage before a distinct commit. Known extra selected rows contradict
a summary omitting them and stop confirmation. Single-selection consume supports
one native unit. Actual acquisition, consumption or storage is not inferred.

Inspection opens one registered inventory/consume/needs/look/messages/map/identity
screen and owns its returned controls. Item, activity, inspection and interaction
children retain the original root Work association, deadlines and cumulative input
ceiling. Phase receipts name their actual kind/operation and restore no authority.
A refused later proposal cannot erase an earlier delivered edit; partial effects
still need interpretation.

An activity root opens ordinary wait/sleep/craft controls. At an owned activity
poll, a typed poll or Observe performs one deadline-bounded observation without
input or Resume. Session, actor, epoch, operator, takeover and control generations
must remain unchanged. Fresh progress, a native output menu or normal return may
advance its checkpoint; ordinary input is still unavailable at a poll. Normal
return closes the phase but proves neither sleep duration nor completed Work.
Retain observed root/child/mission budget overshoot and actual effects. No polling
call renews original deadlines or claims unseen elapsed game time.

Trusted Python `recover_mission` supplies exact six-field transport receipts for
paused activity interruption and its owned answer, without operator-Pause renewal,
a lease or Resume. Native fixed expiry is checked immediately before publication;
pure correlation captures a terminal ACK/time before acceptance or retention I/O.
A later persistence failure stops authority without rewriting that ACK as unknown.
Genuinely unknown delivery retains its identity and cannot be replayed. The ordinary
operator recovery API remains separate. The registered activity adapter now composes
this transport through the existing writer and ledger; public JSON has no raw
recovery executor. A permitted interrupt child first stops ordinary dispatch,
preserving the original operator mark, actor/epoch, root Work and all ceilings.
One bounded fresh paused observation can find natural completion before any
interrupt is sent. Otherwise each interrupt and exact YES/NO answer is charged
as an ordinary primitive mapping. Terminal request/result/clock remain immutable
delivery evidence even without an after-frame or after a failed publication
bookkeeping transaction; a writable settlement atomically binds the native UUID.
No semantic effect or Work completion follows from an ACK.

The private paused phase requires unchanged session/takeover/control generations,
original host consent and nonregressing evidence. Observe is read-only under the
original root/child/mission deadlines. A known frameless ACK requires a fresh
observation, while persistence faults or unknown delivery stop continuation. NO
may leave native activity running while the harness is paused; after a fresh poll
closes its answered confirmation, another interruption uses a new UUID and the
same cumulative root budget. An answered confirmation cannot be answered twice.

Resume is a separate charged activity child, eligible only at a fresh paused
normal/menu boundary under the original operator mark. It grants no lease until
its verified return; root/child/mission time and actor fences still apply before
publishing a new prompt or normal source. A newer user Pause wins throughout.
Ledger9 rejects earlier formats before mutation; there is no compatibility reader.
Reopening restores neither the private phase nor authority. Source tests do not
qualify native gameplay. Already-returned but uninterpretable semantic outcomes
remain unsupported by delivery reconciliation.

### Quiescent player replacement

`handoff` requires settled adopted normal play, the retained owned child, sole
runtime handle/empty queue and reconciled effects. It identifies up to32 retained
checkpoints and every unfinished Work item (up to16); completed/failed Work with
lost supporting bytes also needs attention. Classification uses the coherent Work
projection without truncation. Before stopping input, one shared checker bounds
classification, checkpoints and complete required support to127 distinct sources,
reserving the128th for the future post-Pause source. Required Work must fit a
complete96KiB packet;32KiB of the128KiB handoff envelope remains reserved for the
mission wrapper, maximum query and future source metadata. A narrowly typed
representation refusal sends no input and preserves the original lease, epoch and
bindings. Actual authority, storage and budget failures still stop. The runtime
internally stops input, clears the lease/bindings/map, captures the post-Pause normal
source and checks empty controller/native slots. Atomic issuance records that source,
controller boot, original operator Pause counter, host/native generations and a new
epoch. This is not a public user Pause or restored input authority.

Every `context` request has a required nullable `handoff` field. A successor sets
`{handoff_id, prospective_player_id, actor_role}` while the issuance is live and
unconsumed. Its exact wrapper is journaled and cached (last32), with the packet's
memory version. Ordinary predecessor retrieval uses null and keeps its32KiB,
16-source selective envelope. Bound successor retrieval instead returns every
required Work item, its complete source dispositions and all issuance checkpoints,
independently of query ranking or unrelated Claims, within128KiB/128sources/16Work.
Insufficient requested bytes fail explicitly; required Work is never omitted.
Raw Work assertions retain their eight-source bound. A distinct `WorkView` may
retain up to128 coherent premises, including incomparable or unavailable sources;
its historical/unknown state grants no current progress or input authority.
A claim references one
to four such packets at the current memory version, covering the issued and current
unfinished Work set. Work writes are frozen from issuance through claim until
readmission; permitted Claim corrections require fresh-version retrieval. Packets
retain explicit omissions/unknowns; unavailable old Work evidence is never upgraded
to current progress. A claim may declare up to128 retained sources from those
packets and issuance, including every checkpoint, the post-Pause source and retained support for required
Work. Source loss after retrieval requires a new packet with an explicit unknown
disposition; declaring a nonexistent source read cannot repair it. Classification,
Work support and read declarations share a per-operation128-distinct-source cache;
the exact live checkpoint guards still verify independently. Arbitrary evidence
loss can expand previously terminal Work and invalidate finite fit; preflight is
not a guarantee against later archive corruption. Oversized/lost support stays
explicitly stopped rather than being truncated or replaced by an older assertion.

`claim` records the successor role and source-read declarations, changes the actor
atomically, and remains paused. IDs and declarations are audit statements, not
authentication or proof that an actual fresh agent read an image. The real context
replacement and source inspection require campaign/transcript evidence. A correctable
packet omission/version error sends no input and leaves the original handoff eligible
for another explicit request within unchanged limits. Other authority failures stop.

`readmit` is a separate executable request linked to the exact completed claim and
issuance, with one primitive and finite wall/game limits. Its deadline is the minimum
of issuance, claim, ordinary mission allowance and its own cap. It freshly observes
and compares exact paused native state/encoded pixels, retains that new source,
bounds the initial Observe command-lock/native wait by that same deadline (and
the controller's existing15-second ceiling), charges one Resume before publication,
then obtains a fresh successor lease only
from the verified same normal session. Its typed Readmission correlates the claim,
original and refreshed sources and returned charged primitive. It inherits cumulative
costs/time and cannot borrow create/load authority. Unknown Resume retains its charge
and identity; no automatic replay follows. User Pause, controller/native takeover,
close or reopen revoke the private phase. The intake fence refuses competing queued work while a handoff/claim/readmit
handle is unfinished; cached reads/idempotent receipts and independent Pause remain
available. Atomic receipts survive later cancellation;
reopen validates history but restores no phase, process, lease or Resume.

These boundaries have synthetic controller/ledger/archive coverage. Actual clean-context
player replacement, native gameplay and independent mission acceptance remain open.

Trusted Python `observe_mission(deadline_monotonic, timeout)` uses the original
absolute deadline through command-lock admission and native publication. It grants
no input capability and is absent from public command JSON. A timed queue refusal
is explicit; it never starts another relative timeout after the root expires.
It returns the exact response and its original exchange receipt time as a pair.
Later status captures cannot replace the retained response or renew that receipt.

The CLI exposes `mission-request --request PATH` for a current typed record directly
in project `.runtime/mission-requests/`, regular JSON only, no symlink/script or
arbitrary file path. It checks the same bounded schema before authenticated HTTP,
with no evaluation or implicit retry. Accepted is an admission acknowledgment;
request the immutable operation result by ID and inspect actual sources/effects.
Reusing an ID requires exactly the same payload. Missing network response does not
prove nondelivery. A retained delivery receipt cannot prove semantic success.

The admission gate excludes new mission Start while any raw HTTP command/recovery
is unsettled; raw admission cannot slip past a pending Start. It registers counts
under a short standard lock and rejects busy admission instead of queueing. Native
ordinary/recovery exchanges remain independent under controller channel locks.
While a nonterminal mission exists, raw Observe/input/recovery reject; use the
current typed mission path. Pause and cached status bypass this gate. Raw commands
also bind their original host generation before reading the body, so a delayed
Resume cannot adopt a later Pause. The generation is a trusted Python argument,
not a public JSON field. Terminal history remains visible and owns no execution.

`/api/status.mission` is null or a copied bounded mission snapshot: objective, actor,
epoch, phase/cause, active operation/skill/progress, exact source/receipt identifiers,
remaining limits/reserve, unresolved effects, memory version and diagnostic. The
spectator uses mission Observe and disables ordinary input/Resume/recovery while
nonterminal; malformed mission state stays locked and Pause remains available.
Rendering sends no gameplay or memory request. Normal native input can still take
over; it is not an automatic mission continuation.

`memory_context` is the nullable last durably journaled bounded context packet, copied
for historical inspection. It is query-specific and includes as-of/version/source
IDs, tagged claims/work, omissions and dispositions; status never recomputes it or
claims that its old `current` labels are current now. `spent_inputs` is primitive
cost, not model decisions. A known `not_dispatched` or rejected primitive cannot
change a Claim/Work premise; excluding it from potential effects does not refresh
an old source, align another session or refund its charged admission. Prepared,
published, returned and unknown primitives still require outcome assessment.

`metrics.operations` groups all retained ledger requests by kind, skill and current
state; it excludes read-only calls and pre-admission rejections. `metrics.primitives`
counts every charged admission by current disposition, including rejection,
nondelivery and unknowns. SQLite supplies these cumulative projections at mission
publication; status reads the copied cache, never recent events or journal scans.
Neither metric counts delivered keys, model requests or independent tasks.
`model_requests`, `tool_calls` and `interventions` are null until measured. External
tokens, model time, quota and spending also remain unknown where unavailable.

`activity_phase` is a nullable summary of the current private paused activity:
origin request, checkpoint, stage, interrupt owner and whether it was answered.
It grants no authority, clears on Pause/revocation, and cannot be reconstructed
from `progress.phase`, which is the last reported historical result. The viewer
separates these records and shows bounded readable memory plus raw context;
truncated previews direct the reader to that raw packet. Repeated identical
packets keep their DOM so polling does not reset reading/selection. The source
cache is not a new memory history store. Native/independent-player acceptance
stays separate from the [synthetic viewer inspection](acceptance/2026-10-20-mission-observer.md).

For an eligible published non-lifecycle, non-Resume unknown dispatch, the runtime keeps its original
root, actor/epochs, operator/takeover binding, native request and after-frame
reservation in a private process-local candidate. Before the first later Observe,
it makes one bounded delivery-evidence collection attempt. An exact successful
unclaimed inbox retirement or a validated correlated terminal result may be
retained; missing/claimed files, progress or the next frame alone are not proof.
Collection admits no new evidence after250ms or the caller's deadline, including
after delayed file reads. Filesystem stalls themselves cannot be interrupted by
this software deadline. Host locks do not serialize the native response writer;
an uncaptured terminal result may be overwritten by Observe and stay ambiguous.

The existing journal records collection start, deadline and receipt clocks. A
framed terminal result consumes its original reserved archive capacity before
Observe changes the current source; unavailable or stale frame bytes stop this
path. Exact unclaimed retirement or a frameless terminal result releases only its
unused reservation on explicit reconciliation. Collection alone neither accepts
the response as current, resolves the ledger effect, refunds cost nor sends Resume.

`reconcile` requires the exact original unresolved request, captured private proof
and current fresh paused same-session diagnostic source. A later frame or model
assertion cannot replace missing delivery proof. The uniform closed
`EffectReconciliation` envelope is bounded to32768bytes and has exactly one typed
basis: `DeliveryResolution`, `LifecycleTransition` or `OwnedNormalExit`. Write and
reopen validate its basis semantics and correlate the original request/root/Work,
actor/epochs, primitive/native mapping, canonical native request, independently
retained dispatch binding, collection clocks and source IDs. Reconciliation leaves
the immutable unknown ACK and cumulative charge intact and grants no lease. A
correctable stale/wrong diagnostic selection allows fresh Observe and a new
read-only reconciliation request under the same original bounds; authority changes
or missing proof do not. A proof committed before a crash without its semantic
receipt cannot authorize readmission. Reopen restores no candidate or consent.

`readmit` has explicit closed `handoff` and `recovery` modes. Recovery names the
completed reconciliation, original root and Work, exact sources and live binding.
It requires fresh equivalent normal play, sends one separately charged deliberate
Resume through the existing writer, then acquires the same actor/epoch lease.
Menus, editors, confirmations and activities cannot regain private ownership from
history. Unknown Resume stops without recursive recovery. User Pause/takeover
revokes eligibility while preserving uncertainty/capacity/costs. Registered
lifecycle keeps its own transition handling through the same effect envelope.

A navigation suffix names the original root and unchanged goal/scope/Work. Resume
and suffix share that root's original primitive/wall limits and first game-time
anchor; checks apply before input and after returned effects. Pending continuation
fences ordinary competing skill/lifecycle roots and handoff/claim/readmit until a
verified terminal suffix or explicit stop. Historical phase IDs grant no authority.
This selected source path does not establish semantic success, native recovery or
general recovery from already-returned but uninterpretable outcomes.

Mission/7 and ledger9 migrate all current producers, callers and persisted readers
together. Earlier mission versions, ledger7 and its old untyped effect shape reject
without conversion. Retain old mission artifacts and saves as evidence; only a
separately admitted current mission can start anew. Migration never resets input
costs, renews a stopped attempt or restores execution authority.

## Transport and state


The game enables the bridge only when CDDA_HARNESS_DIR names an existing private
directory. Version 4 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. Each channel admits one live request at a time; the host holds a
process lock for both writers. Gameplay and recovery retain separate identities. Requests carry protocol, unique id, session, expected revision, intended boundary,
human takeover generation,
kind and payload. Size is bounded to 4096 bytes. World entry and exit replace the
session, including a same-process save/reload; relative coordinates belong to that
world lifetime. Stale session/revision commands are rejected, never replayed.
Producer, controller, discovery, CLI, viewer and evidence validation require v4.
Older and unknown versions are rejected; there is no fallback.

Commands: observe, key, action, pause, resume. Observe is side-effect-free in
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

The SDL input loop pumps normal events while polling. RAII scopes span
`input_context::handle_input`, including retries and nested contexts. An explicit
marker at ordinary avatar input distinguishes normal play; deathcam, unknown
DEFAULTMODE callers, activity polling and raw debug prompts cannot inherit it.
The pinned common direction helper marks only its own `handle_input()` wait as a
menu, preserving DEFAULTMODE for native binding lookup. The same `menu_query(category)`
RAII mechanism marks only the pinned item-detail waits in `iteminfo_window::execute`
and `draw_item_info`, plus the comparison wait in `compare_item_menu::show`, with
their original lowercase `default` category. Neither generic name is globally
admitted. The marker activates only in-game with no enclosing scope or active query;
classification requires an exact category match and the stack still empty when
that input scope opens. Nested contexts and callbacks after the wait cannot inherit
permission. The marker clears during return/unwinding and exports no structured
scene. `in_game` means world lifetime, not living-character proof; visible death
still ends an admitted survival study.

The pinned `bodygraph_display::display` input wait uses the same marker with
`BODYGRAPH`, ending before navigation or recursive body-graph callbacks. Its
native bindings and renderer remain unchanged. Unmarked, enclosing or mismatched
contexts gain no authority. This is menu coverage, not a structured health model.

The same exact-owner marker covers the query expression in pinned
`game::cancel_activity_or_ignore_query` with its original
`CANCEL_ACTIVITY_OR_IGNORE_QUERY` category. It ends before cancellation, ignore
or manager callbacks. Empty-stack/in-game/exact-category checks still apply;
unmarked or nested instances remain unsupported. This is an ordinary event
question, separate from the injected pause's owned YESNO recovery. The
[real native probe](acceptance/2026-10-18-activity-distraction.md) verified an actual
feral-cop distraction and ordinary Yes followed by fresh normal play; other choices
and nested negative cases were not exercised natively.
Semantic confirmation uses the existing explicit Yes/No goal at this exact-owned
menu as well as `YESNO`, and still requires the selected registered action and
source/phase/Pause/limit checks. Unknown categories are not promoted by advertising
those names. One answer requires fresh effect assessment; it cannot credit rest
or retry the activity. `IGNORE`/`MANAGER` are outside that binary goal. The
[independent005 failure](acceptance/2026-10-20-independent-mission-fifth-attempt.md)
exposed the former semantic category mismatch; its source correction is not a
new native or independent-mission pass.

The finite ordinary-menu set also includes nearby `LIST_ITEMS`/`LIST_MONSTERS`,
`CRAFTING` and `CONSTRUCTION`, with the engine retaining binding and outcome
validation. Other unknown categories stay unsupported. Entry/exit coverage does
not establish a recipe, activity, target safety, consumption or task outcome.
Activity and debug scopes override enclosing input. Incidental animation polls are
unscoped and cannot dispatch or acknowledge commands. An explicit lifecycle flag
around main.cpp's do_turn loop gates gameplay metadata. Remote input_event delivery includes an
SDL/ImGui adapter for key/text events without sending OS events; native events
are separately observed for takeover.

Each observation has a required `boundary` object: `kind`, nonempty `id`,
nonnegative `control_generation`, `recovery_operations` (zero or one operation), and
`interrupt_request_id` (nonnull only at an owned interruption confirmation). Boundary instances change with context,
session and native takeover, rather than every repaint. The supported matrix is:

| Kind | Observe | key/action/resume | Structured scene |
| --- | --- | --- | --- |
| `normal_play` | Yes | Fresh matching frame and authority required | Player-visible allowlist |
| `menu` | Yes | Fresh matching frame and authority required | None |
| `activity_poll`, `debug_prompt`, `unsupported` | Yes at instrumented polls | Rejected | None |
| `interrupt_confirmation` | Yes at the owned rendered question | Rejected | None |

Menu classification is explicit in the native scope constructor; unrecognized
categories remain unsupported. A registered action is not permission to act at an
unsupported boundary. Recovery uses the separate channel below. Ordinary key/action/resume never
gains permission from a recovery operation. Native keyboard input remains available.

At an eligible rendered boundary the bridge publishes observation metadata and
PNG. Publication redraws the current UI and captures the window backbuffer
immediately before SDL_RenderPresent, checking boundary/session/revision provenance;
the older display-buffer screenshot helper omitted ImGui popup content.
PNG names are immutable session/frame-counter identities, with metadata
published after the corresponding atomic file rename. The viewer grants input
authority only after that image decodes and matches the latest session/revision;
old asynchronous decodes cannot restore a fresh label or authorize an old choice.
Every ordinary action/key/resume wire envelope requires the exact generated
`frame` and a strict boolean `require_exact_frame`; prior field sets reject.
When true, host preflight verifies the retained encoded PNG hash and native commit
encodes the latest cached presented surface through the existing PNG encoder,
compares bounded bytes exactly, then rechecks authority/deadline/boundary/Pause.
False still requires matching saved-frame provenance and the native boundary.
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

## Explicit operator recovery

`Controller.recover(kind, **payload)` is the local Python operator interface.
Authenticated loopback `POST /api/recovery`, explicit CLI recovery commands and
the spectator recovery panel expose this same operator-only boundary. Ordinary
`/api/command` and planner execution reject recovery kinds.
Recovery first pauses and revokes gameplay, then admits its own durable token.
The process lock outlives both writers; a nonblocking control lock prevents two
recoveries. Recovery never waits for the ordinary command lock. The data lock
serializes admission and revocation; shutdown revokes and waits for both writers.

Files are `control.json → control-claimed.json → control-response.json`, with
separate UUIDs, bounded native duplicate ledger and `control-admissions/` records.
An envelope has exactly `protocol: 4`, `id`, `kind`, `session`,
`control_generation`, `authority`, `created_ms`, `deadline_ms`, plus the operation's
fields below. Integer Unix-millisecond expiry is exactly creation plus 2000;
future creation has at most 1000 ms tolerance. Maximum request size is 4096 bytes.
No deadline extension, implicit refresh or automatic retry is permitted.

| Kind | Additional wire fields | Eligibility and delivery |
| --- | --- | --- |
| `request_interrupt` | None | Eligible activity poll advertises it; resolve registered native `pause`, preserving the engine's keyboard-interruption policy |
| `answer_interrupt` | `boundary_id`, `revision`, `frame`, `interrupt_request_id`, `choice` (`YES`/`NO`) | Exact owned rendered query; resolve that choice's active usable binding |
| `continue_debug_once` | `boundary_id`, `revision`, `frame` | Exact raw debug prompt; deliver one Space, never ignore future errors |

Python and HTTP callers supply `expected_session` and `expected_control_generation`.
Answers/dismissals also require `expected_boundary_id`, `expected_revision` and
`expected_frame`; answers add the owning `interrupt_request_id` and `choice`.
HTTP requests use exactly `kind` and the required fields above, with optional
positive `timeout` up to 15 seconds. They retain the ordinary endpoint’s Host,
origin, token, content-type and 4096-byte guards. Malformed input returns 400;
rejected/unknown/controller-error outcomes return 409; other terminal recovery
outcomes return 200. HTTP success reports delivery semantics only. The CLI uses
`--session`, `--generation`, and for prompt operations `--boundary`, `--revision`,
`--frame`; answers also require `--interrupt-request-id` and `--choice YES|NO`.
No surface fetches new authority to silently replace an operator’s decision.

The controller checks freshness and advertised operations. Native rechecks session,
generation, eligibility and rendered prompt evidence, then reads the host token
again at the final commit gate. Delivery latches Pause and increments native
control generation/revision. A later Pause cannot undo already committed input.

Only the specific cancellation questions invoked by harness-delivered native
pause gain interruption ownership. Generic YESNO questions do not. Nested unrelated
input or debug overrides that scope. Each owned question gets a new boundary ID;
returning from a nested boundary requires new matching evidence. Scene metadata
remains exclusive to normal play. Recovery is polled before ordinary requests,
even while an ordinary response is pending, after native input and Pause handling.

A control response has exactly `protocol`, `id`, `status`, `error`, `state`; `state`
is the ordinary current-v4 observation shape. `dispatched` is nonterminal.
`prompt_opened` requires an actual fresh owned confirmation frame.
`answer_delivered` and `dismissal_delivered` report input delivery, even if no new
successful frame is available. `not_applicable` and `rejected` report no applicable
operation or a failed gate. Host timeout is `unknown`; host failures are
`controller_error`. No status alone proves cancellation, error repair or task success.
Transport-only Pause preserves scene revision so recovery can validate the rendered
activity frame that informed admission. Actual input, takeover, resume and boundary
changes still invalidate authority. An activity can finish or reach an unrelated
prompt before claim; inspect the result and observe deliberately, without automatic
refresh or retry. [Native acceptance](acceptance/2026-10-17-native-recovery-planner.md)
separates production gameplay from injected timing and reply-loss probes.

The original gameplay response/pending identity is preserved. Control results may
update passive state but cannot resume gameplay. `control_pending` and
`control_unknown_outcomes` expose separate uncertainty; durable admissions outlive
bounded display history. A matching terminal result can retire only its own
admission. After timeout, only an explicit successful fresh observe after the
native deadline may reconcile the live control slot; passive status cannot rearm
it. Revoke, retire unclaimed work and reject unreconciled claims/active writers
before deliberately admitting another recovery. Keep historical unknown outcomes
and their admissions; reconciliation does not infer what happened or replay input.

Offline migration can preserve older unknown actions through
`historical-incidents.json`: exact `schema: "incident/1"`, `incidents` (at most 64).
Each record has `id` (1–128 chars), `channel` (`gameplay`/`control`), `source_path`
(project-relative under `.runtime/incidents/`, at most 1024 chars), `source_sha256`
(lowercase SHA-256) and `reason` (1–1024 chars). IDs are unique per channel. Startup
verifies containment, file existence, at most 1 MiB and hash, without parsing old
bytes. Invalid references block startup. These surface as `historical_unknowns`
and journal evidence, granting no authority, replay or inferred resolution.

## Designated campaign operator

The lead designates one general-purpose player for a finite mission. It chooses
plans, interprets evidence, retrieves/updates memory and requests semantic skills
and registered normal lifecycle through mission/7. The lead owns source/release
acceptance, finite admission, shared runtime custody, escalation and final
verification. It supplies no ordinary gameplay rescue in the deciding mission.
Explorers/reviewers never send inputs. Actor names and instructions are workflow
controls, not an OS sandbox or authenticated sub-agent capability.

A brief names immutable source/native, admitted world/character, exact command/file
scope, actor/phase, cumulative limits, cleanup reserve and stop rules. No source or
save edits, debug advantages, arbitrary process commands, hidden state, competing
executor or silent budget extension follow from player assignment. User Pause and
native takeover always win. Unsupported or uncertain effects require explicit
source-linked reassessment; they never authorize blind replay or a different actor.

Handoff requires Pause, completed tool handles, no scheduled/queued input, a retained
checkpoint and explicit player quiescence. Cached status alone cannot prove an
empty external tool queue. Fresh-context replacement must use the registered
one-use handoff and retained campaign memory, not lead reconstruction. The runtime
must validate current actor/epoch, sources and original costs before continuation;
a durable receipt or summary restores no lease or Resume. Lifecycle and handoff
adapters remain implementation gates, not permission to fall back to raw commands.

The [first seven-day campaign](acceptance/2026-10-19-seven-day-survival.md) used the
earlier supervised ordinary-input procedure. Its failures, known nondelivery
replans, unknown ACKs, native menu gaps and source-linked decisions remain evidence.
That workflow is historical, not an alternate live campaign ingress. The passive
waypoint planner remains candidate-only for offline studies. Future campaigns need
new prospective authority and actual-player permission preflight; no old campaign
budget, exception, rule allowance or running chat renews admission.

## Closed-loop play and observations


Use goal → bounded skill → one primitive → fresh observation → verification.
Start with movement, menu navigation and single actions. Movement routines have
a small step limit, require normal-game context, and stop on a prompt, no
progress, a visible hostile creature or unknown creature evidence, pause, stale revision or
transport error. Unknown information stops a routine instead of assuming safe.
Maintain observed facts with provenance/age; do not infer an unseen route is
clear. Structured movement fields are relative avatar position, current game
turn, the UI's visible-creature list, and eight neighboring tiles' terrain and
furniture identities only at CLEAR visibility. No item contents, unseen
creatures, absolute world position, or trap state is exported. Movement accepts
only a small known floor/ground whitelist without furniture. Strictly represented
non-HOSTILE creatures may remain visible. Native`hostile:false` means not classified
HOSTILE, not FRIENDLY or safe; creature positions/occupancy are unavailable. An
attempt into an occupied tile can prompt or fail displacement and stops without
retry. New hostility after a returned step stops subsequent input, including at
the target, without undoing that delivered turn. Damage has no
structured field in the first slice and is assessed visually by the planner;
no deterministic damage guard is claimed. The model chooses high-level objectives, while deterministic guards
handle immediate interrupts. VLA/robotics supplies architectural inspiration;
there is no reason to train a robot motor policy for a discrete keyboard game.

Measure verified primitive actions, model invocations, elapsed time, task
completion and harness failures. Compare single-step control and a guarded
routine on a repeatable safe route, with fresh observations in both. Do not
confound fewer model calls with better survival, or claim statistical superiority
from one short demonstration.

A guarded walk checks the next tile even after its final requested displacement.
It can return `stopped` with all requested steps completed if the next tile is
blocked. Read `steps` and the fresh observation; `stopped` does not mean no
movement occurred and must not cause an automatic retry.

An admitted walk aggregate always includes `observation` (the last validated ready
response returned during this walk, or null), `observation_phase` (`pre_step`,
`post_step`, or null), `observation_received_monotonic` (its original receipt clock,
only when the atomic snapshot fully matches that response, otherwise null), and
`terminal_response` (the exact last exchange return, or null before any exchange).
Earlier ingress/admission errors remain plain `controller_error`. Post-step marks
the attempted input, not credited displacement. A timeout can leave only a
pre-action observation: the separate terminal response preserves the unknown;
neither the old image nor a later image supplies its missing acknowledgment.
Unavailable/stale frames and menu responses retain their actual limitations.
These are evidence, not renewed authority or proof of objective success.

Every stopped walk freezes dispatch, requests Pause, revokes the original
admission generation and publishes the sentinel before returning. Even a known
zero-step stop requires explicit successful Observe, player interpretation of the
fresh image and reason, then explicit Resume before another input. Status reads,
internal native preflight and the retained walk image cannot clear the hold.
Queued old generations stay revoked. Complete walks add no hold. The controller
enforces this sequence; semantic reassessment remains the player's responsibility.
The [repair brief](changes/023-walk-reassessment.md) explains scope and migration;
its conservative movement guards remain shared with mission navigation.

## Passive gameplay records and evidence

[Contracts](../harness/gameplay/contracts.py) define eight frozen records:
TaskSpec, EvidenceRef, EvidencePacket, SkillDescriptor, PlanCandidate,
PrimitiveResult, StageResult and RunStatus. Serialized records carry
`schema: "gameplay/2"` and `record_type`; `to_dict`/`from_dict` reject unknown fields,
wrong types, unsupported enums, nonfinite numbers and contradictory completion
claims. JSON is bounded to 1 MiB. The injected planner below consumes these records;
the runtime above connects the passive planner, supervisor and bounded skill.
Broader task formation remains outside this [first slice](design/gameplay.md).

[EvidenceStore](../harness/gameplay/evidence.py) retains successful native-v4
normal/menu/activity/recovery/unsupported diagnostic frames with their actual
coverage. `current()` requires a positively marked normal scene for movement;
`current_boundary()` checks freshness/integrity without granting input permission.
Non-normal references have null game time and no fabricated position/scene facts.
Native `ui` is null or bounded rendered-row coverage only; omitted rows, titles,
filter/count and null selection are unknown, not absence. Inventory rows follow
the visible renderer's selecting columns; the engine's non-selecting cosmetic
selection-summary column is omitted. Other actionable columns, disabled rows,
renderer order and active focus remain represented when visible. This is not
label deduplication: genuine duplicate actionable targets remain ambiguous.
Quantities and complete selected-item coverage remain player interpretations of
the actual screen, not native stock or acquisition facts. Native facts never
include latent/off-page inventory. `pause_origin` is diagnostic; host generation
and process-scoped human takeover count govern continuation checks. Its observation identity is the hash of session plus immutable
frame basename; a transport request ID is not a frame identity. It copies original
PNG bytes outside the evictable bridge cache, verifies hashes and records session,
revision, native timestamp, actual first receipt and `cdda-visible/1` provenance.
It checks bounded PNG signature/size and byte integrity, not image decoding; native
capture and viewer/native graphical acceptance own rendering quality.

At first ingestion, native wall-clock age must be -1000 through 3000 ms. Effective
age adds nonnegative initial lag to monotonic time elapsed since the original
receipt, with a three-second ceiling. Duplicate reads and reopening never renew
that receipt. Clock discontinuity, missing/corrupt source, unsupported boundary,
revision regression, contradiction or session replacement invalidates current
authority. A conflicting retained identity cannot become current again, including
when it was not the current frame; same-revision scene conflicts invalidate
retained peers. Transport-only Pause may produce distinct frames at the same
scene revision: `paused` remains immutable within one frame but is excluded from
cross-frame scene comparison. Actual scene/boundary conflicts still dispute peers.
Historical references remain verifiable but cannot authorize input.
Reopening starts without current authority or a dispatch reservation.
Valid retained metadata remains inspectable when an original image is missing or
corrupt. Reopening records that source as disputed; verification still rejects
unavailable bytes and restored bytes do not clear the dispute. This preserves
memory frontiers without reviving older claims. Invalid metadata and failed
dispute persistence still reject reopening.

Each caller-owned store has one writer and defaults to32frames/64MiB, including
indexed source slots (including missing originals) and orphan files on reopen.
Explicit mission admission may raise retention up to
4096frames/1GiB. Metadata stays bounded to34MiB with separate bookkeeping headroom;
capacity checks reserve worst-case after metadata before dispatch. Each image is at most 32 MiB. Before
dispatch, retain the before-frame and reserve one additional slot plus 32 MiB for
the after/failure frame. Consume or explicitly release that reservation; capacity
failure stops before dispatch and never deletes evidence to make room. The store
itself cannot dispatch. There is no automatic pruning, hidden-state augmentation
or synthetic replacement. Original evidence and bounded tagged interpretations
remain separate. A cross-session PrimitiveResult can retain an after-observation
only as unknown context with no attributed displacement. The bounded native
predicate path was accepted in
[#33](https://github.com/CVX-Hull/enactive/issues/33); see the
[bounded-skill acceptance](acceptance/2026-10-17-bounded-skills.md) for its tested
scope. This does not establish general campaign evidence ingestion.

The evidence store uses format version 3 and exposes `source_status(reference)`
as `retained` or `disputed` after identity/integrity verification. Disputes persist
across newer observations and reopening, including after damaged bytes are restored.
Stale current authority alone does not dispute historical truth. Earlier stores
are archived evidence, not current runtime inputs; create a fresh store for a new
task. Neither historical status grants current input permission.

`authority_generation()` is process-local invalidation history: it advances when
current identity changes, validation invalidates evidence, or the store closes.
Returning to an earlier frame cannot conceal an intervening rejection. It is not
an execution token and is not restored; a new store/memory starts without current
authority.

## Passive task memory

[TaskMemory](../harness/gameplay/memory.py) belongs to one immutable TaskSpec and
EvidenceStore. It retains source facts, explicitly non-factual interpretations
and hypotheses, candidate plans, versioned procedure/failure references and action
results as separate immutable views. It dispatches nothing, advertises no executable
skills and infers no task completion. The store alone retains original frames.

Explicit `refresh` can retain fresh facts; `snapshot` rechecks existing history
without promoting a new observation. Both and `retain_plan` require caller clocks;
snapshots describe that instant, not live authority. Source disputes invalidate
dependent records. Staleness, observation identity or store generation changes,
unknown/conflicting actions, task/session/epoch changes and capacity failures
invalidate candidates. Epoch advance preserves verified history. Task replacement
retires the instance; restart never restores memory or a lease from a journal.

Identical action IDs are idempotent; conflicts preserve the original and mark the
conflict. Recorded displacement must match referenced positions. Cross-session
after-evidence remains unknown context, never progress. Capacity is checked before
append: 128 facts, 32 interpretations, 32 hypotheses, 16 plans, 16 procedures,
32 actions, 64 KiB text including diagnostic reserves, 1024 chars per annotation
and eight source references. No silent eviction. Source-status scans deduplicate
up to the store's 32 frames; freshness/fact/position access may add targeted hash
reads. Retained-byte limits are storage limits, not total I/O measurements.

## Bounded injected planner

[`PlannerPort`](../harness/gameplay/planner.py) belongs to one immutable TaskSpec.
Construct it with `PlannerConfig`, a trusted provider callable and the original
`admission_monotonic` in seconds. This is the same admission origin used by
[evaluation](evaluation.md), with explicit seconds-to-milliseconds conversion.
Construction and delayed first submission do not restart the task clock. The first
invoked request pins the exact start EvidenceRef; continuation cannot replace it
or replenish the original turn/call/time/spend ceilings.

`PlanningRequest` supplies typed task/evidence, accepted skill descriptors, exact
plan/version/epoch, expected outbound/return stage, remaining distance and bounded
public context. The caller owns route progress and capability truth. The provider
receives immutable serialized `ProviderInput` and a cooperative cancellation event,
then returns `ProviderReply(candidate_json, usage)`. It receives no controller or
filesystem handles. Trusted Python injection is not an isolation sandbox.

`submit` reserves cost before invocation and returns a unique call ID. `poll` takes
that ID and the caller's current `PlanningBinding`; mismatches permanently discard
applicability. Candidate JSON must satisfy the existing PlanCandidate schema,
binding, supplied skill/version and exact route semantics. Success returns data,
never permission to dispatch. `cancel` and `close` invalidate pending/completed
candidates; close returns without waiting for a stuck provider. No automatic retry,
restoration or model selection occurs. The runtime supplies the external-chat
provider; deterministic fixtures remain test-only.

| Limit | Contract |
| --- | --- |
| Concurrent/lifetime calls | One physical call; at most ten lifetime calls per port |
| Context/reply | At most 1 MiB each; defaults 1 MiB / 16 KiB |
| Input/output tokens | Network/fixture declared bounds at most 1,048,576 each; defaults 32,768 / 2,048. External chat usage is unmeasured and not enforced by this adapter; bytes are not token estimates |
| Supplied capabilities/context | At most 32 descriptors and 4096 public-context characters |
| Uninvoked rejections | Last 64 audit entries plus total/dropped counters |
| Deadline | At most 30 seconds per call, further limited by task and remaining budgets |

A timed-out call retains the physical slot until its provider exits, preventing
thread accumulation. Deadline, cancellation, close and stale bindings win over late
results. Provider completion is recorded separately from the stop and financial
settlement timestamps. Unknown cost does not keep an already completed call's
measured duration running.

Network mode requires declared credential availability, bounded pricing and a
positive operator-approved spend ceiling/reservation. Missing prerequisites reject
before invocation. These are adapter declarations, not credential discovery or a
billing-system guarantee. External mode requires zero API reservation/spend; it
enforces byte/call/deadline/gameplay bounds but cannot measure or cap the surrounding
Codex chat usage. `external-unreported` explicitly marks unavailable model provenance;
`external-chat-v1` identifies the adapter configuration. Usage fields remain null,
not fabricated zero tokens or subscription cost. Missing cost
or malformed/contradictory usage retains the reservation; valid actual cost can
settle even when token metrics are absent. Over-bound raw usage freezes future
calls before evaluation sanitization. Representable overshoot remains visible;
unrepresentable overshoot is null with a reason. Failed and cancelled calls retain
late cost without reviving their candidate.

`snapshot(cutoff_monotonic=...)` returns immutable accounting and exactly one
`evaluation/1` event per invoked call. Uninvoked rejections stay separate. Record
one snapshot once, with other events in timestamp order. Later knowledge belongs
in a new named artifact; do not append repeated snapshots as duplicate model calls.
Unknown metrics carry reasons. A physically unfinished call is censored at cutoff;
a completed call ends at physical completion even if its reservation is unsettled.

## Passive bounded movement skills

`harness/gameplay/skills.py` implements `MovementStage` and the versioned
`CARDINAL_MOVEMENT` descriptor. `ACCEPTED_SKILLS` contains this one capability.
Descriptors declare implemented predicates; arbitrary strings are not executable
conditions. Cardinal skill version4 supports the remaining part of outbound/return
legs of 1–4 steps using the TaskSpec's original primitive, turn and wall budgets.
The module never sends input, acquires authority, automatically resumes or retries.

Construction binds the immutable task, original task-start/admission, current
checkpoint and a tuple of settled `RouteAttempt(stage, result)` values. The
`summarize_route` function derives task/leg attempts, verified steps, waypoint and
position from retained originals. IDs must be unique, references ordered in the
same session and each before-position continuous with the verified route. Exact
returned steps advance; explicit non-delivery and returned zero consume attempts.
Unknown/dispatched-only or wrong displacement cannot become resumable history.
Only a complete outbound prefix permits return. Caller provenance must originate
from skill settlements or the reviewed revoked non-delivery exception; geometry
alone does not authenticate native receipts. Arbitrary Python callers gain no
execution authority from these types.

A new stage begins at the derived checkpoint and preserves cumulative leg progress,
leg/task proposal counts, original turn reference and admission clock. A terminal
instance never rearms. A complete leg can be freshly verified without creating an
action, even at exactly exhausted primitive budgets, but never after budget overshoot.
There is one constructor and descriptor version; full-leg/count-only callers are
removed. Historical round009 drivers are evidence, not supported current callers.

`propose` returns a frozen `StepProposal` or terminal `SkillEvaluation`. Exactly
one logical action can be outstanding; proposing consumes primitive budget even
if later rejected. Every call requires finite nondecreasing clocks. The checkpoint
and EvidenceStore authority generation must match, all credited/start/waypoint
sources must remain undisputed. The shared `current_guard` requires fresh normal
play, unpaused/unfrozen control, closed bounded visible-creature evidence with
every`hostile` value exactly false, and valid current
position. A registered cardinal action is required even at completion. At an exact,
fully credited target this current-boundary check suffices; before any further step,
the full `guard` additionally requires a CLEAR allowlisted furniture-free cardinal neighbor.
Evidence still requires all eight cells: an invisible future neighbor may omit its
hidden contents, but a missing cell is invalid. Public controller `walk` retains its
conservative next-neighbor check after every step. Prior cardinal descriptor versions
reject; no fallback descriptor or reader exists.

The caller reserves after-frame capacity, rechecks authority and serializes one
input. Logical proposal IDs differ from native UUIDs. The caller must retain an
exact mapping from its journaled action admission and outcome; the controller's
preflight Observe UUID is not an action receipt. No action admission means
`not_dispatched` only when the call's non-dispatch is established. Transport
uncertainty remains `unknown`. A later Observe cannot replace a missing result.

`settle` requires the exact logical ID and before-reference. It computes displacement
from retained observations independently. Verified movement requires the current,
fresh after-frame, same session, advanced revision, nonregressing turn, exact unit
displacement and no intervening generation change beyond that after-reference.
Duplicate results cannot add progress. Malformed or conflicting results cannot
release an unresolved proposal. Unknown/dispatched-only outcomes stop unknown;
rejection, non-dispatch and the first zero/unexpected displacement stop the stage.
Unsupported menu/activity or missing-frame results remain raw external evidence
and cannot be relabeled as normal-play evidence. Release unused reservations.

The final post-step guard runs even at the target: full displacement may coexist
with a blocked/interrupted result. Historical verified progress stays recorded
when older sources become disputed, but completion and new credit are forbidden;
the result becomes unknown. Completion requires the full target and all requested
steps. A committed time/turn overshoot is recorded as budget exhaustion without
undoing observed progress. `EvidenceStore.observation(ref)` supplies an integrity
checked deep copy of retained history; it never refreshes authority or freshness.

The passive supervisor below owns task completion, handoff, epochs and nonprogress
readmission. This is a passive study component; the retired waypoint runtime no longer
connects it to live input. MissionRuntime uses its own typed operation accounting. The [native acceptance](acceptance/2026-10-17-bounded-skills.md)
proves a short manually driven example, not autonomy, trap safety or general survival.

## Passive waypoint supervision

`WaypointSupervisor` has one serialized caller, immutable TaskSpec/run ID, original
start/admission, one EvidenceStore, TaskMemory and PlannerPort. It never imports
the controller or starts a background player. Explicit `start` begins planning;
`poll` admits only a candidate matching exact task/plan/version/epoch/session,
current evidence and remaining route. Changed evidence/generation cancels
applicability instead of rebasing an old candidate. While planning, no intent is
available. The original port owns asynchronous cancellation, physical slot and
accounting throughout continuations.

`propose` offers at most one frozen DispatchIntent bound to run/task, plan, epoch,
stage, skill version and StepProposal. `grants_dispatch_authority` is false.
`settle` requires that complete intent and its exact logical ID/before reference.
Only skill-verified movement earns progress; duplicate results cannot earn credit
twice and conflicting results cannot release pending state. Runtime reserves
evidence, acquires/rechecks the real lease, maps native receipts and serializes
dispatch. Merely obtaining an intent proves none of these.

An unresolved intent expires at publication time plus its bounded wait ceiling.
Every mutating API checks expiry before its own operation; polling and settlement
revoke applicability when `now >= deadline`, retain
pending context and forbid late credit. Explicit non-delivery can release the
pending attempt; other late outcomes stay unknown. Previously credited progress
survives; raw late displacement is evidence, not new verified task progress.

Outbound completion retains a waypoint and starts fresh return planning. Completion
requires both legs, retained start/waypoint/final evidence, fresh current-boundary guard,
current epoch and no unresolved primitive. Starting return planning still checks
the actual return direction with the full next-neighbor guard. Original wall time includes planning
and pauses; task and leg attempt counts include rejected proposals. A stop after
full displacement or budget overshoot preserves progress without claiming success.

Pause, takeover and replacement revoke the epoch and planner applicability. A
published intent remains unresolved until its exact outcome is known. After
revocation, an explicit `not_dispatched`/`rejected` result can record a charged,
no-credit attempt only when retained same-session references show no movement;
this is trusted transport testimony, not an inference from coordinates. Other
late outcomes stay unknown and cannot earn credit or resume. Abandonment retires
the instance; new tasks must be explicit. Session replacement cannot reuse an
old origin. Goal replacement must call `abandon`, then construct a new explicit
task; `invalidate` alone represents a resumable authority interruption, not
replacement. Unknown actions are not automatically replayed or reconciled.

Explicit `continue_task` preserves the original history and budget ceilings and
creates a fresh epoch and remaining-route plan. Already complete legs instead
take a verification-only path without a zero-distance plan or extra action. The
first zero movement stops. Its relevant observable signature must change and all
fresh guards must pass before readmission; changing timestamps/revisions/frame
bytes or asserting success in model text is insufficient. Pausing cannot erase
the blocker. Explicit non-delivery also requires a relevant change, except when
explicit continuation resolves its known operator-revocation cause. This
conservative cardinal policy is not a general semantic monitor.

`status` supplies RunStatus at explicit clocks with `lease_owner=None`; freshness
is not a lease. Accepted completion remains terminal except for explicit
abandonment. Its exact final verification checkpoint stays in status evidence;
later source disputes produce an integrity diagnostic and `fresh=False` without
rewriting historical completion. Foreign-session turns cannot restore reported
task budgets. `pending_intent` keeps unresolved context inspectable. Accounting
and evaluation event snapshots compose with the existing RunRecorder; the caller
and independent assessor supply manifest/outcome and missing measurements remain
unknown. Synthetic tests are not native efficacy evidence. See the
[reviewed design](changes/010-passive-supervisor.md) for ownership, migration and
acceptance. The runtime adds production integration without making this package
a dispatcher. Planning revalidation and non-authorizing status inspection support
slow external decisions while preserving fresh-input guards.

---
owner: maintainer
review_trigger: Native bridge, controller, input, observation or skill change
status: active
---

# Bridge and guarded-play contract

Protocol version: 6.

This is the detailed current contract supporting [architecture](architecture.md).
Authority rules are [S-PROTOCOL](engineering.md#s-protocol-command-and-observation-authority).
Current source is native6/mission10/ledger12/archive5, with procedure/2,
campaign-memory/5 and reflection/2; gameplay/2 is unchanged. The matching rebuilt
native is qualified for ordinary input and the coherent normal lifecycle in
[capture001](acceptance/2026-10-22-native-capture-preconditions.md). That run has
capture-name churn but no checked PNG drift; persistent pixel drift and the
retained-capture commit race remain source-tested, not natively exercised.
[Learning006](acceptance/2026-10-22-discovery-learning-sixth-attempt.md)
and [native001](acceptance/2026-10-22-native-save-refresh.md) provide bounded
graphical qualification; wider input/geometry and the full independent campaign
retain their explicit limits. Dated native5 and earlier results retain their exact
scopes. Portable checks do not prove native engine behavior.

Unsupported versions and alternate response shapes are rejected. Startup validates
stored admissions, claimed requests and any response before restoring uncertainty;
it never converts old records. A dispatched response without its current-format
input identity blocks startup instead of fabricating a synthetic request. An offline
migration must preserve uncertainty and cannot grant authority or replay inputs.
See [coordinated migration](runbook.md#coordinated-migration).

## Controller run ownership

The in-process controller API exposes `acquire_mission(mission_id, epoch,
actor_id, *, operation, expected_session, expected_revision, expected_boundary_id,
replace=None, refuse_changed_context=False)`,
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
For an ordinary operation replacement only, `refuse_changed_context` can report a
typed zero-input applicability mismatch under that same acquisition fence before
rotation. The runtime must then prove complete ordinary custody, source integrity
and resource health after the locks release before retaining read-only Observe
lineage. It never retargets acquisition or applies to specialized lifecycle,
activity, recovery or exit authority.

Ordinary external key/action/walk/resume reject while leased. Existing HTTP/CLI
input reaches this same controller gate; it cannot supply or obtain a capability.
At the controller layer Observe/status, record-only goal and Pause remain
available. HTTP further routes nonterminal mission Observe through typed ingress
and blocks raw input/recovery. The viewer displays mission ownership; a model call
never holds controller locks. Only registered mission operations can request a
lease; service startup, admission and transport Resume never establish identity.

A leased call submits one registered action, permitted key or direct physical
event, using native-v6 observation and input checks. Intended boundary and human takeover generation are
bound in native action/key/resume requests and checked at native commit. The original command admission generation and exact live lease
are checked around queueing/preflight and immediately before atomic publication.
Every walk step uses its original entry generation. Pre-takeover or pre-acquisition
queued inputs cannot become current merely by waiting. Semantic decisions retain
their source-equivalence policy. Direct events retain their informing source while
the actual fresh dispatch capture supplies the native expected triple; this is
physical-event drift permission, not semantic retargeting.

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
`received_monotonic` or null, nullable `preflight` and separate nullable
`processing_error`. Preflight contains the copied final Observe, its original
`received_monotonic` and `expected_image_sha256` or null; direct preflight also
retains its immutable `informing` triple. Preflight Observe is not an action receipt. The
absolute monotonic intent/task deadline is checked after queueing/preflight and
under the publication lock; it bounds both exchanges and the native deadline.
`observation_snapshot()` returns a copied current observation and original first
receipt clock. Reading a snapshot does not renew its freshness.
Live-versus-retained state comparison excludes transport id, timestamp and frame
filename; it retains status/error/frame validity and complete semantic/Pause/takeover
state. This comparison grants neither freshness nor image equivalence. Final
publication preserves the original native-issued preflight capture. Non-spatial,
non-image-conditioned input may use that retained capture after a newer rendering
only while its original clock and complete normalized native metadata remain
valid. Native checks the issued record; the host never substitutes a newer
filename or timestamp. Image-conditioned semantic input, spatial clicks and
recovery retain their applicable current-capture/image/geometry rules. Direct
preflight binds its actual fresh capture under uninterrupted custody, separately
from the immutable model-informing source.
If an image-conditioned ordinary input or spatial capture's filename changes during host preflight while
all existing ownership, complete state, receiver, Pause, pending-work, original
freshness and deadline guards still pass, input is refused before publication
without revoking the healthy lease. Its prepared primitive remains charged and
the batch ends; no native request, ACK or after-source is invented. The runtime
retains only the existing authenticated read-only observation scope across its
operation rotation. Explicit Observe supplies a fresh binding before a distinct
new input intent under the original
mission/prompt limits. This neither retries the old batch nor refreshes its
receipt, replaces its frame or restores expired/lost authority. Combined guard
failures keep their existing stop behavior. Non-image input does not refuse solely
because the latest capture basename changed. Normal lifecycle source policy is
defined below; image-conditioned setup/Resume and paused recovery remain strict.
Known early ordinary nonpublication, such as a changed click mapping before
primitive preparation, uses that same observation scope without inventing a
primitive charge. Prepared refusal retains its actual charge. Processing/storage
faults still stop. Observe may close an exhausted local macro through the existing
closure receipt; it cannot renew its root or spend protected mission reserves.

Native passive captures freshly present and encode. Only unchanged complete
observation metadata, geometry and actual bounded PNG bytes may reuse the current
identity within its original three-second window, checked after encoding/comparison.
The transport id/status/error and capture basename/timestamp are normalized for
that metadata comparison. Reuse preserves the original timestamp, immutable file,
receipt age and retention entry. Explicit id-bearing captures always mint a fresh
identity. Changed/expired/failed captures cannot reuse an older matching frame.
The existing 120-frame native retention deque also retains each issued filename's
original capture timestamp and normalized complete observation metadata. Input
looks up that exact record, compares its metadata with current game-thread state,
then checks its original TTL, current saved/presented clocks and original request
deadline. Unknown, evicted, expired or changed-context captures refuse with
predicate-specific diagnostics. Pixel changes do not renew those clocks.
Image-conditioned input and spatial clicks additionally require the current
capture; registered normal readmission Resume uses its native-state policy while
other Resume callers retain image conditioning. No TTL renewal, automatic retry
or silent retargeting follows. Immutable ACK/UUID,
retained preflight correlation and semantic exact-PNG commit checks remain exact. Recovery
hashes the sampled live PNG outside the Pause lock and fences that same identity.

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

The current MCP presentation is `player-view/2`, marked by `presentation_schema`.
It copies canonical results without changing ledger records, HTTP contracts or
request bindings. The existing32-entry adapter cache retains each complete returned
snapshot (without PNG bytes or the already-excluded historical memory preview).
`enactive_detail(snapshot_id, section)` reveals its exact cached `configuration`,
`metrics`, `receipt`, `progress`, `native` or `source` subtree, with
`grants_authority:false`. It does no I/O, Observe, submission, refresh or cache
renewal. Missing sections return null; unavailable/evicted IDs require an explicit
new snapshot. The original selected snapshot never silently retargets. Actual
source images still use the existing exact source reader.

Default snapshots advertise `detail_sections`. Configuration omits source/native
cryptographic digests; metrics show original game seconds and primitive counts,
while all remaining limits, reserves, deadlines and current uncertainty stay.
Reference slots omit filesystem/hash/retention bookkeeping, preserving opaque
observation IDs and original session/revision/time/turn. Native transport framing
and cached process PID/launch IDs are not default decision data. Full values remain
retrievable in the named detail section. Software still uses the unprojected
mission/source for composition and verification; a hash-shaped opaque handle is
an address, not a request for the model to validate bytes.

Snapshot progress is replaced by `progress_operation_id` only when exactly equal
to the enclosing non-null result with its stable ID. Standalone/pending/different
progress remain complete. Raw native request/ACK payloads are omitted from default
receipts, while delivery, processing/loss diagnostics and correlation remain.
Actions/scene/UI deduplicate only when all match the actually returned source;
missing sources or differing native views retain their information. Selected image
parts and complete explicit source/context/handoff/advice/proposal/operation
payloads are preserved. Projection only touches declared slots, never recursively
prunes arbitrary memory/proof data. The exact field lists live in
[player_view.py](../harness/player_view.py). Canonical evidence stays in the
existing ledger/archive/journal and readers. This is one current presentation;
there is no legacy mode. Source/SDK tests do not qualify actual-host responsiveness.

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

Authenticated `POST /api/mission` accepts one strict mission/10 record, at most65536
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
The later [independent024 mission](acceptance/2026-10-21-independent-supply-shelter.md)
qualifies the bounded integrated gameplay outcome and actual successor continuity.
Native006 retains its actual failure
and exceptional second-child cleanup; later success does not rewrite it.
Neither synthetic UI tests nor tests assuming identity accept an independent mission. Observe likewise cannot adopt
an unexplained normal session. Reopening restores neither phase nor input authority.
The lifecycle Resume checkpoint is refreshed once at entry inside the registered operation
before proposal/publication. The existing guarded Observe must preserve the
[action-specific source policy](#lifecycle-action-preconditions), original actor/operator/takeover and root/child/mission
deadlines. Its journal links old and fresh source IDs without constructing a
lease-bound SourceBinding before a lease exists. It sends no input or grants
readmission by itself. Explicit creation-stage commit, normal save and identity
inspection use the same guarded refresh with typed SourceRevalidation under that
policy; only normal Save start and provisional normal identity entry use native-state
equivalence, while interpreted setup and identity-screen controls retain exact-PNG checks.
Owned create/load/save menu phases also accept `direct` keys/text/clicks through
the same ordinary executor and lifecycle lease. Their typed InputObservation
records entry without claiming semantic equivalence; single physical events need
current custody and a live receiver, not equal pixels or a registered category.
Click geometry and text-batch structural stops remain. Normal provisional play
still permits only registered identity inspection before adoption.
Ordinary semantic controls and navigation likewise capture/revalidate once at entry,
even if the selected source is still fresh. Interpreted controls require exact PNG
equivalence; native-row/navigation decisions retain native-state equivalence.
A replacement that expires before final dispatch still fails. This bounded Observe
cost does not renew requests, phase limits, authority or the freshness threshold.
For menu and semantic controls, the wall deadline starts at original ledger
admission and is capped by the original parent, mission and ending reserve.
The passive policy receives that fixed monotonic deadline before entry refresh;
refresh, lock waiting, repeated proposals and new images cannot renew it. An
informing image's first-seen time remains immutable freshness/provenance evidence,
not the start of a newly admitted child's execution allowance. Time spent preparing
the child still consumes the overall mission and existing root allowances.
Navigation retains its existing additional source-origin passive wall cap and
original continuation clock; this control repair does not extend a route.
[Entry-refresh rationale](changes/053-operation-entry-refresh.md).
Explicit mission Observe on an already-owned ordinary prompt is a new look, not
automatic revalidation of an old input decision. It may retain changed pixels,
labels or menu categories as a new checkpoint under the original root, Work,
actor, game anchor, deadlines and cumulative costs. Old image age alone does not
prevent looking again; retained evidence must remain intact and undisputed.
Before capture, after capture and before checkpoint advancement, the runtime
checks current ownership, session/control generations, user Pause/takeover,
ready/unpaused/error-free capture, original limits and settled delivery. Prepared,
published or unresolved unknown primitives prevent advancement; historical unknown
ACKs with separately resolved effects do not. A changed menu produces an
observation transition, not a SourceRevalidation or renewed authority, and clears
derived quantity-editor proof. A genuinely equivalent menu may preserve that proof
and its exact-PNG revalidation. Actual normal return closes only that prompt and
reports observed budget overshoot without certifying the original goal.
The player must make a new input decision using the new source. Semantic input
entry refresh remains strict as described above. Direct entry
uses the non-equivalent InputObservation and live receiver policy below. An
explicit Observe has its own original fifteen-second deadline, capped by mission
and ending reserve. Global ownership, mission input/game/wall and trace guards
run before local macro limits. If the ordinary prompt's root input, wall or game
cap is exhausted, the immutable Observe result records `macro_closure` with old
root/checkpoint, fresh source, detection time and the specific limit before only
the private prompt is cleared. It neither rewrites the old root result nor emits
a complete PhaseReceipt, certifies success or renews any allowance. Lifecycle,
exit, registered activity/recovery and unsettled delivery use their own paths.
From the fresh owned menu, an adopted player may explicitly select a new direct
root under the original mission limits. Old-source/stale queued children refuse
at writer consumption while healthy custody survives.
Save refresh precedes operation rotation and preserves its original normal-game
time anchor. Changed state, Pause or expiry still stops input.
An atomic controller snapshot keeps a frame's first-seen clock; a command reader
can receive the same frame's matching ACK later. Terminal delivery checks validate
both clocks independently, without imposing their ordering or renewing either.
The original terminal clock remains finite, after its preflight and bound to the
exact native UUID/state. Authenticated historical ACK retention does not impose
dispatch freshness retrospectively; source/PNG integrity checks remain. Snapshot mismatch
records its actual state and valid clock for diagnosis before stopping. These
historical receipts never restore a revoked phase or input consent.
The harness-enabled SDL ImGui context disables only input-text cursor blinking
through its existing library option; exact encoded PNG equivalence is unchanged.
There is no image masking or tolerance for changed content. Other animations can
still invalidate an old interpreted decision. Ordinary setup controls may cancel
unfamiliar dialogs and return to the owned main menu. That menu-only path can use
the separate normal cleanup below; unadopted/wrong normal-session cleanup remains
unsupported.
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

Create/save/load roots require null `work_id` and empty `identity_claim_ids`.
The shared pure submission validator rejects violations before client submission or
receiver queue admission, so a malformed draft cannot itself revoke a lease.
It does not discard supplied fields or retry; a new corrected request must pass
every live guard. Identity adoption still uses its exact lifecycle child; Finish
may cite completed Work. Pause, missing evidence, budgets and storage failures
retain their existing stopping behavior. This syntax refusal grants no authority.
The underlying record validator still reads original rejected request history;
old failures are retained unchanged and cannot become executable through reopening.

Cached process facts are last samples, not a liveness guarantee. Shutdown journals
any owned child without signals; reopening restores no process handle. Only a
validated committed OwnedNormalExit resolves that launch's historical custody.
Otherwise attempted/uncertain launches remain unavailable, with no PID adoption.
Process absence or exit code alone cannot prove a normal save/exit.

Registered `exit` covers the same owned untouched MAIN_MENU, a verified explored
pre-character menu, or a menu reached by this child's validated SavedCheckpoint.
Menu-only eligibility requires the original correlated returned create/load Resume
and settled same-root controls: returned effects or authenticated native-rejected
nondelivery. Rejected inputs retain charges/correlation but add no game effect.
Unknown input, transition candidates or normal-play evidence prevent this cleanup.
Every retained intermediate remains an owned menu in that session. The current MAIN_MENU must match the last authenticated
input revision and original control/operator/takeover lineage; its pixels and
selection may differ from launch.
Read-only Observe can adopt that private cleanup checkpoint; it grants no input.
Ledger write/reopen/orphan checks audit the original Resume mapping/source IDs;
runtime and EvidenceStore own retained source and live-authority checks. An earlier exit must
have no inputs or its fully settled verified No; pending/unknown exit inputs cannot
be skipped by a new root. This does not handle arbitrary setup rollback or restore
consent after user Pause.

While that menu-only create/load phase is still live at MAIN_MENU, a new
source-bound `exit` root may explicitly request its abort. It audits the original
Resume and settled exploration, actor/operator/custody, no normal segment/candidate
or pending slot, then verifies a new native capture of that current owned menu.
It revokes setup through internal recovery without
sending input or changing the launch checkpoint. The plain partial result reports
`cleanup_requested`, not an exit proof or a phase receipt. The original request
epoch remains historical; the ledger's pause advances its current epoch. Separate
Observe must establish the fresh internally paused menu, followed by
a new finite normal-exit root. Neither step restores the old setup phase, renews
mission ceilings nor overrides a concurrent user Pause/takeover. Other setup
screens, unknown inputs and historical reopened evidence cannot use this
abort path. The saved branch requires the exact final
normal endpoint and its original first menu source, even after later observations.
It retains the launch's original operator mark.

Reload staging follows actual native transitions: a returned MAIN_MENU world
confirmation entering UILIST arms the private character-selection stage; return
to MAIN_MENU retires that stage. Before a load confirmation is dispatched, the
rendered UILIST must have one enabled admitted-character row and that exact row
must be selected. No literal `Load Game` label or alternate label reader arms the
stage. That row gate applies to the semantic shortcut; ordinary controls still
require post-transition exact identity and this mission's SavedCheckpoint.
Unknown delivery retains its original UUID/reservation; diagnostic Observe,
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
For a registered expected transition, a changed-session terminal ACK remains
unknown. Diagnostic Observe retains the actual after-frame against that dispatch's
exact capacity reservation; a separate
same-root current-epoch request records LifecycleTransition and reconciles effect
without relabeling the ACK. Only then may explicit provisional readmission inspect
PLAYER_INFO. Its semantic helper permits only QUIT to return; ordinary menu input
can interact with that visible screen and the player must interpret any change.
Neither path grants normal-play authority before separate truthful identity
Claims/adoption. Ordinary dispatch checks the actual preflight receiver, so a
menu becoming normal play cannot carry a provisional physical key into gameplay.

Every actually published lifecycle input with a potentially committed effect also
retains private dispatch correlation when it was not a registered expected transition.
An authenticated native rejection means no input committed: retain the original
charge and receipt, create no uncertain-effect candidate, and preserve only healthy
existing custody. Explicit Observe and a new selected request may continue under
the original limits; rejected FINALIZE/NEXT_TAB leaves the form awaiting control.
Creation-proof readers authenticate this nondelivery without counting it as a
confirmation or stage reset. Pause, takeover, processing faults and unknowns retain
their stops; transport publication alone is not a game effect. After an uncertain
or unexpected outcome, explicit Observe can retain the actual same-session or changed-session
image under the original owned launch, actor/operator/native custody, dispatch
reservation and wall/observation limits. This diagnostic-only result exposes source
IDs and its limitation, without an executable lifecycle phase, transition/effect
proof, adoption, Resume, lease, map, memory or game-time credit. Input allowance
exhaustion alone does not prevent this zero-input observation. Known supported same-session
feedback clears provisional correlation; registered expected transitions retain
their separate handling. Reopen cannot reconstruct the private candidate. Normal
cleanup of an unadopted or wrong-identity session remains unsupported; a diagnostic
image is not a recovery or normal-ending guarantee.

While that reconciled create/load phase remains paused awaiting identity, Observe
may refresh its diagnostic checkpoint without activating the ledger or acquiring
a lease. The committed transition and exact terminal effect are revalidated through
the ledger's existing proof checks, tied to the immutable first normal source and
reconciled epoch. The owned child/operator/actor/native lineage must remain exact;
prepared/published or unreconciled inputs and live leases/pending slots reject.
Exact PNG/native equivalence, original refresh deadlines, game and capacity checks
still apply. Repeated diagnostic refreshes change only the checkpoint and retained
evidence costs. They cannot Resume, adopt identity or reconstruct a reopened phase;
the next explicit same-root lifecycle child still charges its own Resume.
Use `enactive_lifecycle` with lifecycle scope, the same create/load operation and
root, and no identity Claims or Work; then request inspect/character_identity in
that lifecycle scope. The separate readmission validates the complete committed
transition/effect proof before activation and dispatch.

A premature exact identity-inspection request can return a correctable zero-input
refusal while retaining that private paused phase. This requires the same proof,
owned process/operator/actor/epoch, quiescent delivery, exact current source and
native PNG, support integrity, original deadlines/game/root/input/mapping limits
and retention/cleanup headroom. No refresh, activation, lease or Resume occurs.
An aged intact checkpoint may explain the missing prerequisite without becoming
fresh; a NEW explicit lifecycle request still performs its full refresh and input
preflight. Wrong metadata/support, changed pixels, user Pause/takeover, unsettled
input, uncommitted proof, lost child or exhausted limits keep stopping behavior.
An immutable blocked result is never reinterpreted as permission or success.

### Lifecycle action preconditions

Lifecycle source policy distinguishes the registered action from incidental pixels:

| Private checkpoint/intent | Refresh and dispatch precondition |
| --- | --- |
| Owned normal Save at `save_start` | `native_state`; preserve the original root, first-normal identity, budgets/deadlines and interaction lease through refresh, then perform the existing single checked lifecycle rotation before Save dispatch. |
| Creation/load `awaiting_identity` at normal play | `native_state` for provisional refresh, its separately charged registered Resume and entry to identity inspection. Original committed transition/effect proof, owned child, actor/epoch/Pause lineage and subsequent identity Claims/adoption remain mandatory. |
| Setup forms/rows, identity screen, explicit confirmations and other lifecycle checkpoints | Existing exact-PNG policy; a normal-context rule cannot authorize a different stage or operation. |
| Ordinary create/load/save menu controls | InputObservation at entry and ordinary dispatch at actual preflight; no pixel or menu-label equivalence. Original custody, root limits, click geometry and text structural stops remain. |

Creation effect proof authenticates the existing explicit character-stage commit:
a returned same-root lifecycle NEXT_TAB from NEW_CHAR_DESCRIPTION into YESNO,
followed only by owned confirmation receivers through the correlated terminal
input. Returning to a form/list/main menu retires that commitment. The terminal
may be semantic or physical; no final key or question spelling proves freshness.
The explicit stage operation remains a CDDA integration constraint, not a general
game-family capability. Save proof retains the original registered Save action
and uninterrupted owned menu interval. Returning to the same adopted normal
session cancels Save without a saved-checkpoint claim, regardless of the key.
Raw source/proof checks on reopen establish history and never reconstruct a lease.

The same selected rule is recorded in SourceRevalidation and Resume lineage and
used through runtime/controller/native preflight. A normal image change under
equal complete native state does not require another Save decision merely to
wait for equal pixels. This does not claim image equivalence, renew an aged source
or reconstruct a phase from history. Pending/unsettled input, lost custody,
Pause/takeover, changed required native state, archive faults and exhausted original
limits still stop. Image-conditioned choices, spatial input and registered
recovery retain their own stronger checks. No automatic input retry or general
liveness guarantee follows. Source regressions and actual native qualification
remain separate evidence lanes.

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
Native007 qualified the selected actual creation/save/load path. The later
[independent024 mission](acceptance/2026-10-21-independent-supply-shelter.md) exercises
actual fresh-context memory and the full bounded supply/shelter/lifecycle outcome.
[Native008](acceptance/2026-10-20-confirmation-correction.md) additionally qualified
world and Save local-question rejection followed by new exact guarded correction,
identity/adoption and normal save/exit/stopped Finish. Original unknown delivery
and the failed independent001 remain retained; Native008 itself accepted no
independent gameplay objective.

### Skill request binding errors

Construct `expected_session`, `expected_revision` and `expected_boundary_id`
programmatically from the single chosen retained observation associated with the
cited source. Use existing JSON tooling; do not copy opaque fields independently
or carry an earlier boundary across a focus change. A source reference alone does
not expose every native field: read its declared observation metadata and verify
the pair. A draft, cached status or historical source grants no input authority.

An existing lifecycle phase whose selected source/native tuple no longer names
its exact current checkpoint refuses with zero proposals and the current source. This
request error preserves a healthy owned phase, lease, epoch and original limits;
the player must select current evidence for a new request. It never retargets or
replays the old request. Archive verification, live custody, Pause and delivery
faults retain their existing failure paths. Roots without an existing phase retain
their prior rejection behavior; this is not a new setup recovery path.

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
their direct create/save/load root, including ordinary controls and provisional identity inspection;
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

The writer checks an internally inconsistent expected triple, additional
informing sources outside the current actor/authority, or a menu draft selecting
native-row control without its supported representation before adapter mutation
or refresh only when the cited current source is exact and available,
and any explicit perception names that same source. Existing read-only ownership,
authority, original budget and integrity fences must still pass. Then it records
plain blocked without Observe, rotation, reservation or input, retaining the
original phase/checkpoint, lease/epoch and deadlines. It never substitutes fields
or certifies freshness. Same-ID results are immutable; a new corrected request
traverses every normal guard. Request counts and elapsed time remain spent.
This also covers item-selector menu activation and quantity-editor drafts that
conflict with the immutable item root. Prompt ownership and control representation
are separate checks: a malformed semantic request does not prove lost ownership.
The player may correct the semantic request, cancel, or use an ordinary direct
key/text/click child under that same healthy root. It need not discover the
preferred semantic adapter before trying an ordinary interface action. Such input
retains ordinary entry/dispatch lineage, click geometry, original limits and
delivery accounting;
it supplies no typed quantity-editor attestation or automatic success claim.
The runtime never sends a rescue key or chooses the player's next action.
Null menu perception selects the native UILIST row policy, not automatic image
interpretation. A source without that policy's menu/category/purpose/coverage
requires an explicit source-bound visible-control interpretation. The eligible
zero-input refusal preserves the original scope; it does not infer the view,
switch adapters, relax native-state equivalence or provide a general recovery
from EvidenceError. If healthy visible state or pixels changed during an ordinary
draft check, refuse without input and require explicit Observe before correcting
the request. Preserve the original root and costs; specialized lifecycle/activity/
exit proofs remain strict. No automatic corrected request or rescue key is sent.
Additional skill sources must share the current mission, actor, epoch, controller
boot, host Pause generation and native takeover generation. Older observations
within that authority may support a transition; historical sources from an earlier
phase belong in memory/Work instead. Private lifecycle/paused-activity skill
checkpoints without a live source binding accept only their exact current source;
specialized lifecycle transition proofs retain their separate typed requirements.
Unknown additional IDs are draft errors, but
all known retained cited sources are checked for integrity/dispute before any local
refusal. This never drops a source from an executed request: a current-only copy
is used solely to prove live eligibility for rejecting the original draft.

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
That action must actually be registered in the selected evidence. The sole key
case is a rowless `POPUP_WAIT` whose registered actions, excluding only the pinned
producer's ubiquitous `toggle_language_to_en`, are exactly `ANY_INPUT` and
`COORDINATE`: explicit dismissal sends one existing `SPACE` key. A registered
`QUIT` retains cancellation instead. Other missing actions, extra controls or
represented choices block with zero proposals; no aliases or answers are guessed.
A delivered dismissal returns partial for verification and never answers
a newly opened question. Upstream UILIST cancellation is conditional; category
admission alone does not establish that cancellation is enabled. First worldgen
cancel support does not implement a general setup-abort lifecycle.
[Native010](acceptance/2026-10-20-menu-dismissal-qualification.md) exercised the
narrow binding correction, then failed normal ending on the old generic-QUIT
mapping. [Native011](acceptance/2026-10-20-registered-dismissal-qualified.md)
subsequently qualified actual registered UILIST dismissal and normal ending.
The failed Native010 attempt cannot resume; later qualification does not rewrite it.

MissionLimits permits at most 691200 game-seconds (eight days); its default remains
43200 seconds. Each finite admission must budget normal ending work before its
selected cap. Every input lane checks known canonical game cost before publication,
including lifecycle and readmission. Reaching or exceeding the cap prevents input
and revokes authority after settlement, with no cleanup exception. Startup has no
adopted game clock and keeps its existing independent guards. Read-only Observe
and user Pause do not dispatch inputs. Raising the software maximum extends no
existing admission and establishes no native survival outcome.

`lifecycle(operation=finish)` is the sole normal finish route. Stop carries only
its Pause reason; former Stop `finish` fields and every prior mission schema
reject. The current mission/10 contract migrates CLI, viewer, requests, results and fixtures
without an alias or automatic old-admission import. Campaign-memory/5, procedure/2,
reflection/2, SQLite ledger12, native wire6 and archive5 migrate together; gameplay/2
remains unchanged. Prior accepted reports and raw older mission/memory/ledger
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

A returned navigation input may open an ordinary in-game menu in the same session.
Mission/10 records a `navigate` PhaseReceipt (`operation=navigate`) and terminal
partial result, retaining the verified prefix and last verified route position.
The menu has no scene; the opening input receives no displacement credit or retry.
Inspection uses the existing menu outcome `inspected`, with no input; standalone
inspection skills still require normal play. Only exact current retained feedback with unchanged attribution/authority can open
this phase. Unknown delivery and activity/debug/unsupported boundaries do not.
Explicit menu/editor children share the original root, Work, deadlines
and cumulative primitive ceiling. An interrupted recovered suffix transfers to
that original root and game anchor before its continuation closes. No interaction,
item or activity root is borrowed. A normal return closes the prompt; a subsequent
navigation plan is a new explicit player choice, not automatic route continuation.
Ledger10 validates the selected child links and closed receipt variants on write
and reopen; historical records restore no private phase or input authority. The
[repair brief](changes/055-navigation-menu-interruption.md) records rationale and
qualification limits.

Mission/10 retains explicit item units (`items` or `charges`) and root/select/commit
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

Inspection requests one registered inventory/consume/needs/look/messages/map/identity
action and owns its returned controls. Consume inspection uses the default-bound
`eat` action and its all-items selector, also used by item-consume roots; the
separate by-type `open_consume` menu has no default key binding. This is one chosen
engine action, with no automatic alias/fallback or consumption credit. CDDA may
return another outcome (both consume entry points first try `eat_here`); interpret
the actual result before further input. Item, activity, inspection and interaction
children retain the original root Work association, deadlines and cumulative input
ceiling. Phase receipts name their actual kind/operation and restore no authority.
A refused later proposal cannot erase an earlier delivered edit; partial effects
still need interpretation.

An activity root opens ordinary wait/sleep/craft controls. Item, inspection or
interaction roots may also enter an ordinary native activity after their own
attributed input, such as consuming an item. At a retained owned activity poll,
Observe performs one deadline-bounded observation without input or Resume;
typed activity polls remain restricted to their original activity root and goal.
Session, actor, epoch, operator, takeover and control generations
must remain unchanged. Fresh progress, a native output menu or normal return may
advance its checkpoint; ordinary input is still unavailable at a poll. A returned
menu retains the original root kind, Work, game anchor and limits and requires
fresh player interpretation through that root's existing explicit controls. It
does not permit another root, arbitrary menu adoption or automatic answers.
Normal
return closes the phase but proves neither sleep duration nor completed Work.
Retain observed root/child/mission budget overshoot and actual effects. No polling
call renews original deadlines or claims unseen elapsed game time.
These existing PhaseReceipt stages now settle and reopen coherently for the
supported owned roots; no field, enum, persisted shape or native/tool version
changes. Navigation activity support remains outside this contract. Historical
failed observations remain failures; no private phase is restored on reopen.

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
Ledger12 rejects earlier formats before mutation; there is no compatibility reader.
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
bindings. `checkpoint_ids` identifies retained source observation IDs, not memory
Claim or Work IDs; `unfinished_work_ids` identifies the exact complete unfinished
Work set. Unknown checkpoint references and omitted/extra Work IDs are correctable
draft errors before stopping input. The player selects actual retained sources or
retrieves complete current Work and submits a NEW explicit request while still
eligible. No handoff, source substitution, Resume or budget renewal is automatic.
A known checkpoint source with unavailable bytes remains an evidence failure. Actual
authority, storage and budget failures still stop. The runtime
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
of issuance, claim, ordinary mission allowance and its own cap. Select the original
issued `post_pause_source_id`, even if a separate Observe returned a newer source
after claim; readmission performs its own bounded refresh. If the native binding
matches but that issued source is omitted, the ledger refuses before admission
with the exact required ID and no input. An explicit NEW corrected request remains
subject to all original live handoff, source, Pause and resource guards; this
feedback grants no eligibility or Resume. It freshly observes
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

These boundaries have synthetic controller/ledger/archive coverage and actual
clean-context retrieval, image presentation, one-use claim/separate readmission
and useful continuation in the [bounded024 mission](acceptance/2026-10-21-independent-supply-shelter.md).
That functional evidence proves neither security isolation nor causal memory benefit.

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
remaining limits/reserve, unresolved effects, memory version and diagnostic.
`coordinate_scope` is nullable passive metadata derived from the current retained
normal-play source's adopted timeline: mission ID, session and coordinate epoch.
Normal source publication verifies adoption and creates the current session map;
status reuses that scope after the existing retained-source integrity check,
without repeating lifecycle verification or observing native state. It is null
before adoption, without that map or retained source, and at menus without a
current normal-play source. The coordinate epoch
is the adopted session's timeline index, **not** the mission/actor `epoch`, Pause
generation or native revision. A successor copies this returned scope for bound
context retrieval instead of guessing an index. It grants no freshness, lease,
claim or Resume, and the live handoff guard still validates the request against
its own checkpoint-derived scope. Current persisted formats and tool argument shapes are
unchanged. The diagnostic string retains earlier refused-operation errors after
later successes; inspect current operation results and phase/ownership/provenance
before concluding that a historical string is a current fatal fault. The
spectator uses mission Observe and disables ordinary input/Resume/recovery while
nonterminal; malformed mission state stays locked and Pause remains available.
At a terminal mission, recorded last-command errors are labeled historical;
controller/native snapshot diagnostics are explicitly not gameplay instructions.
Their complete text remains visible, including genuine faults. Current local
transport/manual errors remain separate. These labels neither establish that a
fault is stale nor reconcile unknown effects or authorize Resume.
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

Mission/10 and ledger12 migrate all current producers, callers and persisted readers
together. Earlier mission versions, ledger7 and its old untyped effect shape reject
without conversion. Retain old mission artifacts and saves as evidence; only a
separately admitted current mission can start anew. Migration never resets input
costs, renews a stopped attempt or restores execution authority.

## Transport and state

HTTP JSON uses Python's finite compact UTF-8 codec with the same encoding basis
as canonical bounded advisory contexts. Per-record parser caps do not become
aggregate spectator-status response caps; each client retains its own limits. A valid Unicode job and its offered/
claimed envelope must fit the unchanged client response cap; ASCII escaping and
pretty-print expansion are not extra admitted context. Request, job and transport
bounds remain separate checks. Serialization changes no job claim or authority.

### Ordinary discovery and procedure data

Mission10 keeps `skill_kind=direct` on the existing writer, with a passive ordinary
policy separate from semantic menu planning. Its closed goal contains `input`,
`intent`, `expected` and `interrupt_allowed`. Input is one explicit ASCII/named
key with modifiers, one left/right click bound to the selected PNG's geometry,
or at most24 printable BMP text scalars. Unsupported supplementary Unicode refuses
before input in the pinned16-bit widget build. Text expands into separately
charged scalars with fresh feedback, no implicit Enter, and stops for changed
receiver structure, identical pixels, lost eligibility or uncertain delivery.
Single keys/scalars permit visual drift at an owned ordinary receiver without
requiring equal pixels, category names, labels or click geometry. A click keeps
its original mapping and refuses changed geometry; it never follows an old label.

The exact informing request/source remains immutable. Non-authorizing
`InputObservation` links its `original` and entry `current` SourceBindings under
the same mission, epoch, actor, controller, Pause and takeover, with exactly one
store-generation advance. It asserts no equivalence. Only the first ordinary
intent after entry has non-null `input_observation`; `source_before` names entry.
The prepared intent's expected triple and published native request/frame name
the actual final preflight; after revision checks compare with that preflight.
Entry age does not invalidate a separately fresh dispatch reservation. Semantic
SourceRevalidation and stronger semantic/native-state preconditions remain strict.

Captured-source custody and action applicability are separate. A verified source
is an immutable as-of sample with its original receipt. Binding it, returning
Observe or exposing it as `current_source` does not require the native application
to stay visually unchanged during storage. Verify uninterrupted lease/actor/epoch,
controller/operator origin, session, takeover, native control and Pause origin,
both samples' health and clock/revision integrity. A future clock, regressed
revision, contradictory same-revision scene or changed immutable capture remains
a fault. Mission status names the latest retained sample, separately from the
spectator's newer native frame; neither grants input authority.
Ordinary current-source availability also requires its existing live published
binding/custody; stopped or unbound history is not exposed as current. Explicit
owned lifecycle/activity/handoff/exit checkpoints retain their private paths.
The initial activity poll and an exact owned launch/saved-menu checkpoint also
retain their existing presentation path. The owned menu requires the original
operator mark, admitted/active mission and retained running native-process custody;
Pause or process exit cannot expose it as current.
During a live handoff, a newer read-only Observe may remain current under the
existing handoff epoch/controller/Pause/source proof. The issued post-Pause
checkpoint stays fixed; selecting the newer sample for readmission still refuses.
Passive malformed-state validation makes the current sample unavailable without
closing result collection; execution still fails closed. The controller checks
the archive's clock/revision progression at ordinary entry and late refusal
fences, and immutable capture/custody at the final retained-proof comparison.

Semantic entry refresh still requires positive state/image equivalence before
input. A verified non-equivalent refresh publishes actual fresh evidence, advances
any ordinary prompt through its observation transition and returns blocked with
zero input. Later healthy applicability drift returns a typed local refusal only
after complete custody, queue, source-integrity and global-budget checks. Preserve
the root, deadlines, charges and read-only Observe lineage; never restore an old
store generation, retarget an input or resume a remaining text suffix. Custody-only
preflight retention is permissible solely on this proven nondelivery branch,
selected before strict semantic retention and ending before reservation/preparation.
Registered creation, Save/identity, handoff, activity, recovery and exit retain
their stronger proofs. [Design059](changes/059-observation-custody-and-applicability.md)
owns the rationale and source-versus-native evidence limits.

Native direct requests require `require_exact_frame=false`. The gate still checks
the actual fresh receiver, session/revision/boundary/frame provenance, custody,
Pause, expiry, capture health and click mapping. Healthy typed pre-input refusals
retain ownership; malformed custody, integrity/storage faults, competing writers
and global exhaustion retain their stops. Structured facts distinguish those
cases, rather than matching diagnostic strings. Unknown delivery retains the
original identity, collection, reconciliation, charges and no-replay policy.

A correlated ready ACK is returned delivery even for unfamiliar or superseded
evidence. Authenticate it before fallible acceptance, journaling or retention,
then settle once with its actual `source_after` or explicit `evidence_loss` before
Pause/current publication. The ledger's bounded `native_ack` contains protocol,
id, session, revision, status, native error, paused/pause origin, takeover,
timestamp, frame validity/identity and boundary. Scene/UI/geometry remain in the
original archive/controller journal. Separate `processing_error` and `evidence_loss`
never rewrite known delivery as unknown. Publication bookkeeping failure can bind
the native UUID atomically while settling the prepared intent. When that mandatory
settlement commits and custody/evidence remain healthy, the publication diagnostic
does not itself force Pause. Raw controller processing faults, lost archive/current
evidence and lifecycle proof failures still stop. SQLite owns the row transaction; no redundant post-ACK preflight-file sweep or second journal is
required. Failed storage remains failed storage: reopening without durably saved
ACK evidence is conservative. A returned receipt without after evidence stops
with explicit loss and cannot construct a gameplay/2 PrimitiveResult requiring it.

ACK retention is historical and non-promoting: it preserves bytes, identity,
original receipt clocks and recorded lag without changing current source/session/
generation. `source_after` always names that ACK capture. A separately validated
actual current snapshot preserves its first receipt and pays its own frame/byte
cost when distinct. It never replaces after. A different current source ends the
operation partial and stops a text batch even when pixels match. Healthy native
advancement beyond the retained ACK also ends the batch and requires Observe;
the actual ACK and its receipt remain unchanged. An owned prompt
advances only from eligible actual current evidence, retaining root, Work, consent,
deadlines and costs while clearing incompatible focus/quantity assertions.
After known returned direct input, an absent or aged independent snapshot can
retain a read-only ordinary scope. Its checkpoint remains the entry source; the
ACK remains historical. The private scope records the exact authenticated operation
generation, preserving root, Work, actor/epoch, game anchor, deadlines, consent and
cumulative costs. Its PhaseReceipt stage is `awaiting_observation`, status marks
`observation_needed` and exposes no current source. At writer consumption, skills
and lifecycle requests refuse without input, charges or a new Pause. Explicit
Observe verifies that generation, unchanged store lineage, retained integrity and
all existing custody/global limits before capturing and publishing a fresh binding.
It clears the read-only marker, advances an actual menu or closes on actual normal
return; a locally exhausted root instead gets the immutable `macro_closure` above.
It never renews old-source authority or resumes a failed lease. Healthy local
game-time overshoot returns partial work (`macro_exhausted`), retaining mission
ownership; normal return ends that root and an owned menu awaits Observe closure.
An exhausted ordinary prompt child is refused before operation rotation or
controller input preflight, with `macro_exhausted` and no primitive charge.
This applies to ordinary and semantic roots, without recognizing a menu type.
The original root and prompt remain unchanged until explicit Observe commits
their closure. Custody, retained-source integrity and global limits must still
pass; local exhaustion cannot hide their failure. Refusal does not choose a new
root, close a menu or establish task success.
Request/root allowance exceptions are typed separately from mission, clock,
storage and authority failures. A trusted read-only classifier can translate only
eligible, healthy ordinary-scope expiry into the controller's existing known
unpublished refusal. The controller checks fatal ownership/Pause/competing-work/
boundary/capture fences before preserving custody, including at final atomic
publication. It never classifies a published request this way. Any allocated but
unpublished admission must be removed successfully; a prepared primitive keeps
its original charge and settles not-dispatched. The existing authenticated
rotation records a read-only `awaiting_observation` scope; explicit Observe still
owns fresh evidence and any macro closure. Lifecycle, registered activity/recovery
and actual global exhaustion are excluded. Passive terminal verification may
establish a skill's result before declining an additional input proposal.
The same known-unpublished path covers final-preflight filename churn for
ordinary leased semantic key/action proposals, including an activity's START at
normal play. It does not cover paused activity/recovery or lifecycle input.
The controller preserves its actual preflight capture and checks all fatal
guards before rejecting; it neither retargets the native frame nor retries.
Before retaining read-only lineage, the writer independently verifies current
custody, original source/storage health, mission limits and the receipt's actual
preflight state and clocks. A rejected status alone is insufficient: early
image/geometry refusals can precede controller preparation. Navigation reports
`awaiting_observation` both before movement and after a verified prefix; that
prefix and every prepared charge remain recorded. Only explicit Observe and a
new player choice can continue; no old suffix resumes. Source regressions cover
these cases; an actual native occurrence and complete campaign remain separate.
Unknown delivery, actual clock/session regression, controller processing,
integrity/storage, lifecycle/activity/recovery and global exhaustion keep their
stopping paths. A missing current frame alone neither undelivers an ACK nor
permits another scalar. These are source-tested paths; new native/graphical
qualification remains pending.

Direct roots require an adopted normal character, or an explicit new root from a
fresh owned menu after the ordinary macro closure described above. Prompt children
retain the original root, Work and cumulative limits. Direct input cannot borrow
lifecycle/navigation authority or establish typed quantity proof. Activity children
of a direct root use operation `direct`, the original expected outcome, time cap
and interruption consent; they invent no wait/rest/craft success. A returned input
is partial work requiring player verification. The [mixed-input design](design/mixed-input.md)
specifies mappings and pending integration work; source/component checks do not
qualify a new native binary, graphical play or actual non-CDDA support.

Every skill record has nullable`procedure`. A selected root names owning mission,
immutable revision ID, root use ID and its applicability judgment. The structured
producer derives the use ID from the original request ID. Children must use null
and inherit the root selection; changing style cannot replace it. Original
requests, root links, primitives, results and cumulative costs provide automatic
usage feedback. Neither an input ACK nor that linkage proves semantic success.

Admission has required nullable`learning`. A policy freezes the exact environment,
at most4 closed library mission pins (ledger/index SHA256), advisory actor and
finite reflection limits. Procedure/2 records live in the existing immutable
memory table. Full qualified ancestry resolves heads; branches/missing parents
refuse. Episodes must join actual settled request/source evidence. Candidates can
be tested; disputed/retired heads are inspectable and cannot be newly selected.
The current player judges descriptive applicability; memory grants no authority.

The read-only library uses SQLite over hash-verified bytes, shared archive locks
and derived project paths. It never reopens a runtime writer, restores a phase or
imports old-world Claims/Work as current facts. Only current ledger12/archive5
input with the exact native6/mission10 procedure environment is eligible. Earlier
native5/mission9 archives and learning004 remain immutable historical evidence,
unmountable as current libraries. A fresh current-contract learning005 must close
normally before its library can support fresh seven-day003; old failures never resume.
Authority-blocked retained sources are historical evidence, as in EvidenceStore:
a bounded unique list of valid retained blocked IDs does not itself dispute their
bytes or support. Library exports remain historical and `grants_authority:false`.
Disputed sources, malformed/foreign blocked IDs, missing/changed images or invalid
episode/effect linkage still refuse; no archive is rewritten to gain eligibility.

Campaign-memory/5 uses qualified procedure refs, records, source requirements and
explicit omissions, rather than placeholder lesson IDs. Decisions retain selected
procedure support. Complete handoff fit checks include every procedure head and
its evidence, reserving room for the future post-Pause frame. Claim declarations
include`read_procedure_sources` alongside current-world source reads, within one
aggregate128-source bound. Source-read declarations and retrieval are evidence
of presentation/selection, not proof of attention or causal improvement.

The [procedure/exchange design](design/procedure-learning.md) owns the asynchronous
integration boundary; current records use reflection/2. One private
RegisteredReflection composes a per-admission
passive mailbox/cache with the existing writer and SQLite ledger. Four routine
root skill decisions coalesce a job; failures, recovery and handoff boundaries
can trigger earlier work. Each job retains original request/result order and
cutoff, memory version, bounded sources/procedures and explicit omissions.
Interrupted missing results and individually oversized rows remain omitted
original evidence rather than preventing subsequent review. Pending overload
coalesces future work; exhausting finite reflection limits leaves it unreviewed.

The existing loopback server exposes authenticated `/api/reflection/command`,
`result`, `next`, `source`, `frame` and `proposal` routes. Passive reads/waits use
cached data and retained source images without the input queue/lock or Observe.
Only the passive `next` read permits up to40 seconds, using the existing condition
notification to return promptly on work or closure. Other transport/tool waits
remain at most15 seconds. The adapter caps claim/collection at15 seconds and the
remaining original call allowance; no job window or resource limit is renewed.
The project's60-second MCP timeout is unchanged. This reduces possible idle model
round trips; it does not eliminate idle turns or promise a hard wall deadline.
Only the existing writer applies claims/submissions. Claims charge their original
finite wall window without refund; software receipt time judges submission
lateness separately from writer queue delay. Rejected advisory commands retain
zero-input outcomes; storage faults remain faults. Original command receipts
restore into a passive cache without requeueing. No model computation runs there.

Structured tools expose `enactive_reflect_next`, `enactive_reflect_source`,
`enactive_reflect_submit`, `enactive_reflect_result` and `enactive_advice`.
The result tool collects an original command ID even after an adapter loses its
volatile claimed-job cache. Advisory source reads do not populate the player's
source-read cache. Candidate proposals never auto-adopt, Resume or confer input
authority; the player owns adoption, applicability and later choices.

Normal finalization temporarily seals advisory ingress before draining received
commands and settling offered/claimed bookkeeping as unreviewed/unknown. It
preserves costs and original outcomes, and does not claim the host actor stopped.
While finishing or temporarily sealed, next-job reads offer no work and retain
their original bounded wait before returning `idle`. Only a terminal mission phase
or permanent writer shutdown returns `closed`; temporary sealing never tells an
advisory actor to terminate. A canceled preterminal finish, including refusal at
the authoritative terminal ledger write, reopens healthy nonterminal ingress
without renewing old jobs. The settled advisory phase is published before the
Finish result becomes collectable. Storage faults and already committed terminal
history never reopen. Ordinary Save/Exit/Load does not seal advisory ingress.
Permanent shutdown wakes waiting readers; terminal history accepts no late writes.
Actual host concurrency, actor quiescence and real discovery/reuse/counterexample/
fresh-context/overlapping-play qualifications remain separate delivery057 work.


The game enables the bridge only when CDDA_HARNESS_DIR names an existing private
directory. Version 6 uses atomic JSON files and PNG snapshots, avoiding another
server thread in CDDA. Each channel admits one live request at a time; the host holds a
process lock for both writers. Gameplay and recovery retain separate identities. Requests carry protocol, unique id, session, expected revision, intended boundary,
human takeover generation,
kind and payload. Size is bounded to 4096 bytes. World entry and exit replace the
session, including a same-process save/reload; relative coordinates belong to that
world lifetime. Stale session/revision commands are rejected, never replayed.
Producer, controller, discovery, CLI, viewer and evidence validation require v6.
Older and unknown versions are rejected; there is no fallback.

Commands: observe, key, action, direct, pause, resume. Observe is side-effect-free in
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

Every observation has required`frame_geometry`: null when`frame_ok=false`,
otherwise positive window/output width and height (maximum16384 each) and a
four-integer viewport`[x,y,width,height]` within the full output. Width/height
must be positive and total output at most16777216 pixels. Native capture retains
the full default render output in a matching allocation. Direct click geometry
must equal that retained geometry and the final current geometry; its PNG pixel
maps separately to engine window coordinates and widget output coordinates.
The harness uses an internal synthetic pointer, never moves the Mac pointer or
requests focus, and consumes balanced widget press/release through bounded normal
render frames. Postcommit consumption failure is dispatched/unknown with fault
Pause, never a known zero-input rejection or a later success acknowledgment.

The SDL input loop pumps normal events while polling. Context RAII scopes span
`input_context::handle_input`; receiver RAII spans the existing game-thread
`input_manager::get_input_event()` render/poll path. Required boolean
`boundary.input_receiver` attests that the live receiver matches the actual top
context and depth. A raw receive without an active context cannot attest ordinary
eligibility. Receiver entry/exit alone does not mint a revision or boundary ID.

Ordinary contexts may have unfamiliar category/action names; no menu-name catalogue
grants permission. Explicit avatar scope anchors normal play; deathcam/unsupported
owner, debug, activity and owned interrupt restrictions take precedence through
nested contexts. Inherited restriction does not confer inherited recovery power:
activity interruption and its owned query remain tied to their actual owner/depth.
Incidental animation polls are unscoped. The explicit lifecycle flag around
main.cpp's do_turn loop gates gameplay metadata, not character identity. Visible
death still ends an admitted survival study. Semantic adapters retain their narrow
registered-category/control coverage; ordinary receiver support does not qualify
a structured health model, recipe, consumption or other effect. Historical
[direction](acceptance/2026-10-18-native-direction-menu.md),
[distraction](acceptance/2026-10-18-activity-distraction.md) and
[native5 discovery](acceptance/2026-10-21-discovery-learning-fourth-attempt.md)
results retain their tested binary and scenario scopes.

Each observation's required `boundary` has `kind`, nonempty `id`, nonnegative
`control_generation`, boolean `input_receiver`, zero or one `recovery_operations`
and `interrupt_request_id` (nonnull only for owned interruption confirmation).
Boundary instances change with context, session and takeover, rather than repaint
or receiver timeout retries. Remote key/text/click translation feeds the existing
engine/widget path without OS input; physical takeover retains precedence.

| Kind | Observe | Ordinary input | Structured scene |
| --- | --- | --- | --- |
| `normal_play` | Yes | Live receiver, fresh dispatch evidence and authority; semantic policy also applies | Player-visible allowlist |
| `menu` | Yes | Live receiver, fresh dispatch evidence and authority; semantic policy also applies | None |
| `activity_poll`, `debug_prompt`, `unsupported` | Yes at instrumented polls | Rejected | None |
| `interrupt_confirmation` | Yes at the owned rendered question | Rejected | None |

Observe and an advertised action alone grant no permission. Recovery uses its
separate exact-owner channel below; nested help cannot borrow it. Native keyboard
input remains available.

At an eligible rendered boundary the bridge publishes observation metadata and
PNG. Publication redraws the current UI and captures the window backbuffer
immediately before SDL_RenderPresent, checking boundary/session/revision provenance;
the older display-buffer screenshot helper omitted ImGui popup content.
PNG names are immutable session/frame-counter identities, with metadata
published after the corresponding atomic file rename. The viewer grants input
authority only after that image decodes and matches the latest session/revision;
old asynchronous decodes cannot restore a fresh label or authorize an old choice.
Every ordinary action/key/direct/resume wire envelope requires the actual generated
`frame` and a strict boolean `require_exact_frame`; prior field sets reject.
When true, host preflight verifies the retained encoded PNG hash and native commit
encodes the latest cached presented surface through the existing PNG encoder,
compares bounded bytes exactly, then rechecks authority/deadline/boundary/Pause.
Direct must use false, allowing changed pixels while retaining actual saved-frame
provenance, receiver/custody and click-geometry checks. Semantic/lifecycle policies
retain their stronger requirements; false alone is never input authority.
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
is the ordinary current-v5 observation shape. `dispatched` is nonterminal.
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
and registered normal lifecycle through mission/10. The lead owns source/release
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

Mission navigation's `ObservedMap` is a bounded candidate cache, not durable world
memory or a lifetime exploration budget. Each valid projection keeps its current
position and four cardinal coordinates within512cached coordinates, atomically
evicting oldest other coordinates by their newest cell/anchor source revision,
with deterministic coordinate tie-breaks. Both cell and anchor entries are removed
together. A test configuration too small for one footprint refuses before mutation.
Eviction never removes retained frames or Claims, renews authority, changes scope
or refunds mission costs. An old route may become blocked/unknown until reobserved;
ordinary observation/input and fresh guarded navigation continue within the
original mission limits. Source integrity, regression, session, Pause/takeover and
uncertain delivery remain separate stopping conditions. This process-local cache
change adds no persisted or tool format and no compatibility path.

[Contracts](../harness/gameplay/contracts.py) define eight frozen records:
TaskSpec, EvidenceRef, EvidencePacket, SkillDescriptor, PlanCandidate,
PrimitiveResult, StageResult and RunStatus. Serialized records carry
`schema: "gameplay/2"` and `record_type`. Constructors and `from_dict` reject
unknown fields, wrong types, unsupported enums, nonfinite numbers and contradictory
completion claims. Nested values are immutable; `to_dict` encodes these already
validated frozen values into fresh containers without repeating schema validation.
Raw serialized input and explicit trust-boundary receipt checks retain their
validation. JSON input is bounded to 1 MiB. The injected planner below consumes these records;
the runtime above connects the passive planner, supervisor and bounded skill.
Broader task formation remains outside this [first slice](design/gameplay.md).

[EvidenceStore](../harness/gameplay/evidence.py) retains successful native-v6
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

For current ingestion, native wall-clock age must be -1000 through 3000 ms. Effective
age adds nonnegative initial lag to monotonic time elapsed since the original
receipt, with a three-second ceiling. Duplicate reads and reopening never renew
that receipt. Clock discontinuity, missing/corrupt source, unsupported boundary,
revision regression, contradiction or session replacement invalidates current
authority. A conflicting retained identity cannot become current again, including
when it was not the current frame; same-revision scene conflicts invalidate
retained peers. Transport-only Pause may produce distinct frames at the same
scene revision: `paused` remains immutable within one frame but is excluded from
cross-frame scene comparison. Actual scene/boundary conflicts still dispute peers.
Historical terminal retention instead validates bounded historical age and original
lag without imposing current dispatch freshness or promoting authority. Archive5
records the retention kind, so reopening preserves that distinction. Historical
references remain verifiable but cannot authorize input.
Reopening starts without current authority or a dispatch reservation.
Valid retained metadata remains inspectable when an original image is missing or
corrupt. Reopening records that source as disputed; verification still rejects
unavailable bytes and restored bytes do not clear the dispute. This preserves
memory frontiers without reviving older claims. Invalid metadata and failed
dispute persistence still reject reopening.

Each caller-owned store has one writer and defaults to32frames/64MiB, including
indexed source slots (including missing originals) and orphan files on reopen.
Explicit mission admission may raise retention up to
8192frames/2GiB. These shared mission/store/library ceilings support a prospectively
sized campaign; existing default budgets and original admissions do not grow.
Metadata stays bounded to34MiB with4MiB bookkeeping headroom;
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

The evidence store uses format version 5 and exposes `source_status(reference)`
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

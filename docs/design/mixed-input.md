---
owner: lead
review_trigger: Ordinary input schema, native keyboard/mouse handling, phases or evidence migration changes
status: proposed
---

# Mixed skills and ordinary interaction

The player should use skills for efficient familiar work and ordinary keys, text
or deliberate clicks for discovery. Both go through the same mission writer;
switching must preserve the original work, costs and uncertain outcomes. This
selected design for [#176](https://github.com/CVX-Hull/enactive/issues/176) now has
the source implementation and bounded evidence recorded in
[delivery057](../changes/057-discovery-learning-campaign.md); unqualified features
and future target handles below remain proposals. Current [architecture](../architecture.md) and
[protocol](../protocol.md) remain authoritative.

Further design follows the charter's CDDA-class constraint and P-GENERALITY.
The ordinary input mechanism must remain available when a shortcut cannot
interpret a novel or changed menu. Game-specific native events, semantic bindings
and lifecycle attestations belong at the integration boundary. #190 fixes the
known zero-input item-draft revocation; #191 tracks broader recovery and portability.
Source support for clicks is not full mouse qualification or cross-game support.

The source now implements the ordinary-input foundation through the existing
writer, with optional semantic preconditions above it. Current contracts are
native7/mission11/ledger12/archive6, with procedure/3, campaign-memory/6 and
reflection/2; gameplay/2 is unchanged. Physical events may reach changed ordinary
screens under uninterrupted custody, while semantic refresh remains strict.
Explicit Observe permits a new decision from a changed healthy owned prompt,
clearing stale quantity proof while preserving original scope and costs. Known
ACK evidence remains immutable and separate from any actual current snapshot.
The [delivery impact map](../changes/057-discovery-learning-campaign.md#ordinary-input-foundation-and-artifact-impact)
and #191 identify remaining game-integration and qualification gaps. The new native7 export adds separate literal marker evidence. Historical native6
[capture001](../acceptance/2026-10-22-native-capture-preconditions.md)
qualifies ordinary input and normal lifecycle on the rebuilt boundary. Its checked
PNG pairs match despite changed capture names; persistent pixel drift and the
retained-capture commit race remain source-tested, unexercised natively. Earlier
graphical qualification is bounded by the [normally closed learning006 report](../acceptance/2026-10-22-discovery-learning-sixth-attempt.md).
Its scoped procedure library was eligible under its original contract; it is
historical and unmountable under mission/11 and procedure/3. A fresh independent seven-day campaign
remains unaccepted. Image-conditioned semantic/spatial final-preflight capture churn shares the existing
known-unpublished refusal/explicit-Observe path, with independent custody,
source/storage, mission-limit and original-preflight checks. This is source
support, not new native qualification. Non-image input preserves its issued
preflight capture and original TTL under equal complete current native metadata,
even after a newer rendering. Normal lifecycle follows its action-specific
[source policy](../protocol.md#lifecycle-action-preconditions); other
image-conditioned lifecycle and paused activity/recovery remain strict. No native
filename retargeting or automatic retry is introduced.

The [organic-discovery crosswalk](organic-discovery.md#cross-check-against-prior-work)
retains prior mixed-control research, campaign findings and memory distinctions.
Independent013's unbound consume action demonstrates a catalogue/binding trap;
it does not demonstrate mouse support or general learning. Player-learned
procedures (#177) and background reflection (#178) remain separate work.

## Selected ordinary-input migration for review

This selected #191 boundary is implemented in current source. The heading retains
its original review link; it does not mark the migration as pending. The lead
selected these decisions from the actual002 failure and independent controller/
receiver reviews. The research crosswalk preserves their evidence basis and limits;
source review and a matching build do not qualify real graphical behavior.
The [ordinary-input protocol](../protocol.md#ordinary-discovery-and-procedure-data)
and [schemas](../../harness/gameplay/mission_contracts.py) own exact current shapes.

**Physical-event drift policy.** A direct request means the explicitly selected
key, scalar or coordinate, not an inferred semantic target. It may reach a changed
ordinary screen under the same owned session and uninterrupted actor/Pause/custody.
Retain immutable model-informing sources, entry observation, actual final preflight
and terminal evidence separately. Do not call changed evidence equivalent or change
the physical event to follow an old label. Clicks keep their original geometry;
changed mapping returns a known refusal and fresh evidence for another decision.
Keys/scalars do not require identical pixels or click geometry. Optional semantic
shortcuts retain their appropriate exact-image/native-state preconditions.

**Receiver attestation.** Native7 retains the mandatory boolean
`boundary.input_receiver`. It attests a live ordinary engine event receiver, not
semantic coverage or a desired effect. Instrument the existing SDL
`input_manager::get_input_event()` with a game-thread RAII receiver scope before
its existing rendering and polling; the active input-context scope supplies the
actual top context. A raw receive with no active context cannot attest eligibility.
Remove the menu-name catalogue as the ordinary-input boundary: ordinary contexts
can present unfamiliar names/actions. Preserve explicit deathcam/unsupported-owner,
debug, activity and owned-interrupt precedence through nested scopes; none gains
ordinary permission merely by opening another context. A context's name alone
cannot establish normal play. Receiver scope exit revokes receiver availability;
publication and commit attest the active receiver, not an earlier cached scope.
Existing key/text/click translation feeds that same receiver and widget path.
Receiver entry/exit must not itself mint revisions or boundary IDs on every
timeout retry; only actual observed boundary/presentation changes do so. Inherited
restrictions prohibit ordinary input but do not grant inherited recovery powers:
activity recovery operations remain tied to their exact owner/depth, as does the
existing owned interrupt query. Nested help or a transient context is not an
activity-interruption receiver merely because an ancestor is an activity.

**Native contract.** All ordinary/control requests and observations use native7;
native5 rejects. The direct event payload stays key/text/click. Direct requests
must use `require_exact_frame=false`; their exact transport session/revision/
boundary/frame are the actual fresh dispatch capture, not the old model image.
The final native gate still checks ownership token, Pause, pending work, expiry,
receiver and capture health. Click geometry must match the actual receiver's
current mapping; keys/scalars have no coordinate precondition. Semantic action/key
and lifecycle operations retain their admitted stronger policies. Typed expected
pre-input refusals preserve healthy ownership; unrelated/native storage, malformed
custody and integrity exceptions remain hard faults and set fault/Pause. Keep
physical takeover precedence. The host reads structured status/Pause/custody facts,
never error-string patterns, to distinguish them. Post-commit uncertainty remains
unknown. A new explicit Observe can read after a healthy authenticated rejection;
that read does not treat a rejected packet as input-ready or clear an actual fault.

**Host lineage and one writer.** Mission10 adds `InputObservation`, a closed
non-authorizing record containing `original` and `current` SourceBindings, with
the same mission/epoch/actor/controller/Pause/takeover and exactly one store
generation advance. It records a new ordinary entry observation without an
equivalence claim; SourceRevalidation remains semantic equivalence only.
Primitive intents gain required nullable `input_observation`, non-null only for
the first ordinary proposal after entry. The original source must inform the
immutable request and the current binding must name its actual before-source.
Use the existing source-before/preflight/after fields for dispatch lineage.
For ordinary intents, `source_before` is the entry source; `expected_*` and the
published native request name the actual final preflight, and after-revision
checks compare with that preflight. Entry age cannot invalidate a separately
fresh actual dispatch reservation.
Final ordinary preflight retention permits changed evidence under the same live
custody without promoting or rewriting model evidence; correlate its actual
session/revision/boundary with the published native request. Preserve required
capacity reservation and durable preparation before publication. Retain strict
equivalence for semantic preflight. No second executor, history or transport.
Captured evidence remains an immutable as-of sample when a healthy newer native
view appears under the same custody. Binding and Observe preserve that sample's
original receipt; semantic applicability is checked separately. A non-equivalent
semantic entry refresh publishes fresh evidence and refuses input. Later ordinary
applicability drift uses the existing typed refusal and explicit-Observe lineage
after complete integrity/custody/resource proofs. Custody-only retention of a
semantic preflight is selected only for proven nondelivery and must end before
reservation or preparation; strict retention failure is never caught and retried
with weaker rules. See [design059](../changes/059-observation-custody-and-applicability.md).

Actual window-resize qualification remains in [#181](https://github.com/CVX-Hull/enactive/issues/181).
The archive treats changed geometry at one revision as contradictory; the current
native presentation increments revision for turn/UI changes and samples geometry
separately. Source tests with revised synthetic geometry do not prove that native
resize advances revision. Reconcile that coupling with real resize evidence in
the wider-geometry work; do not claim qualification or silently waive the archive
contract from a synthetic passing test.

**Delivery and further input.** A correlated ready ACK is returned delivery even
when its screen is unfamiliar, unclassified or already superseded by a later
observation. Its actual capture is historical evidence; readiness for another
input is checked separately. Retain original receipt clocks without imposing the
three-second dispatch freshness window retrospectively on settled history.
Use a genuinely historical, non-promoting retention path: it preserves original
receipt clocks, bytes and recorded lag without changing current session/source/
generation or rejecting a receipt merely because a newer revision exists.
Archive5 reopening validates this historical age rather than imposing the old
three-second current-observation bound. Missing/corrupt capture remains explicit
evidence loss. Preserve validated ACK/request correlation before fallible snapshot
acceptance, logging, unlinking or after-frame retention; a subsequent failure
records a separate stop while keeping known returned/rejected delivery. A crash
without durably retained ACK evidence still reopens conservatively; failed storage
cannot be made reliable by a convincing in-memory receipt.
Storage/integrity failure can still stop the run, but cannot rewrite an
authenticated returned input as an unknown ACK. Unknown or missing ACKs retain
existing identity, collection, reconciliation, costs and no-replay rules.
Known unpublished visual/representation/geometry refusal returns evidence while
healthy ownership survives; actual custody, Pause, competing writer, exhausted
mission resources or unavailable required trace capacity still stops input.
An image-conditioned/spatial frame-name refusal is classified only after all original fatal
guards pass. Non-image native dispatch instead verifies the original retained
issuance, complete current metadata and original clocks; it never rewrites the
requested frame. A settled unpublished
ordinary refusal retains the existing authenticated `observation_generation`
scope across operation rotation, including the first refused prompt child;
explicit Observe must publish a fresh binding before another input. This is
read-only continuity, not a new recovery framework or rebinding of old evidence.
Prepared refusal retains its charge; an early unprepared geometry refusal adds
none. Processing/storage faults still stop and exhausted local roots close
through the existing Observe receipt without extending their allowance.

Use the existing ledger receipt for a closed, bounded `native_ack` projection:
protocol, id, session, revision, status, error, paused, pause_origin,
takeover_generation, timestamp_ms, frame_ok, frame and boundary. Preserve the
native diagnostic separately from `processing_error` and explicit `evidence_loss`.
Scene/UI/geometry remain in the original after archive/controller journal; the
compact projection is delivery evidence, not a complete native observation or
proof of semantic effect. Bound and validate the worst-case encoded receipt under
the existing65,536-byte ceiling without truncating correlation facts or enlarging
the81,920-byte receipt reservation. Request.frame binds preflight;
native_ack.frame binds after, whose identity must match when retained. Do not
require a ready ACK's new frame to equal its preflight frame.

Authenticate and preserve the ACK immediately, make the bounded retention attempt,
then settle once with either source_after or explicit loss before stopping or
publication. Never terminally settle missing evidence and later rewrite that
immutable receipt. If publication bookkeeping failed, validate correlation and bind
native_id atomically with known terminal settlement from prepared, extending the
existing control fallback. Apply mapping checks during settlement and reopening.
Returned-without-after settles known delivery, stops and raises explicit evidence
loss; it must not construct a `gameplay/2` PrimitiveResult that requires after
evidence. No gameplay format change or second feedback path is needed for a storage
failure. Failed settlement remains failed storage, with available proof preserved;
reopening is conservative when no durable ACK evidence exists. Scoped independent
architecture review accepted this approach; the runtime now implements it.
Source tests and review do not establish real native gameplay behavior.

Apply S-CODE's platform-contract rule here. SQLite owns atomic row settlement;
the bridge's existing publication/ACK contract owns delivery correlation. Keeping
the validated preflight metadata through dispatch removes post-ACK archive rereads
from authentication. Do not add another before/preflight file-integrity sweep on
every ACK. Ordinary archive consumption/reopening/audit detects actual loss at its
boundary without rewriting already settled delivery. Native frame counters order
same-revision captures within one millisecond; this is transport ordering only,
not a new game clock or authority mechanism. No additional journal, storage service
or recovery framework is selected.

Keep `source_after` as that authenticated ACK capture. An independently captured
actual current snapshot may be ingested/published separately, under fresh receiver,
same-session/custody, original first-receipt clocks, Pause and capacity checks.
Expose its source separately; never substitute it for the ACK's after-source.
Charge a genuinely distinct capture its actual frame/byte cost. If current differs
from ACK, end the operation partial, even when pixels match; no automatic next
scalar or semantic retargeting. Advance any prompt checkpoint from validated
current evidence, preserving root, Work, deadlines, consent and cumulative costs
and clearing incompatible quantity/focus assertions.

If no eligible current capture exists, an old checkpoint cannot silently become
current. Read-only Observe must account for the operation's authenticated lease
rotation before another input: the existing prompt guard's exact host/store
generation assumptions are insufficient unchanged. Preserve the original scope
under the same live actor/epoch, lease, operator mark and session; require fresh
evidence and a newly published binding before input. Storage/custody/global faults
still stop. Independent scoped architecture review accepted these distinctions.
The current source implements the direct-input fallback with the existing private
prompt: an exact authenticated `observation_generation` is read-only, the old entry
checkpoint remains historical, `awaiting_observation` tells the player to Observe,
and the writer refuses input until a fresh capture publishes a binding and clears
the marker. Original scope and costs survive; no new journal, retry or authority
format is introduced. Local game overshoot yields partial work without revoking
healthy ownership; an owned menu closes through explicit Observe, while normal
return has already ended the root. Global/clock/custody faults and unknown delivery
retain their stopping paths. Scoped synthetic regressions and independent review
are source evidence only. Capture001 above supplies its separate bounded native
qualification and exact build pins. Normally closed
[learning006](../acceptance/2026-10-22-discovery-learning-sixth-attempt.md) qualifies
bounded graphical ordinary discovery/procedure application;
[Native001](../acceptance/2026-10-22-native-save-refresh.md) qualifies one unit-scale
click and normal lifecycle. Non-unit/wider mouse behavior, cross-game integration
and the later local-exhaustion correction remain separate unqualified lanes.

**Ordinary policy and scope.** Extract the direct policy from semantic menu
planning; it remains passive and uses the existing writer's intents/results.
One key/click/scalar is the base operation. An optional text batch retains its
finite scalar count and stops for player reconsideration on changed receiver
structure or no visible progress; that stop does not undo known scalar delivery.
Masked text still permits individual-scalar experiments. Switching to direct
invalidates incompatible quantity/focus assertions while retaining the original
root, Work, actor, deadlines, interruption consent and cumulative costs. Local
macro exhaustion must remain distinct from exhaustion of the whole admission;
no silent root renewal or new allowance follows.

An explicit Observe may end an exhausted ordinary macro without ending a healthy
mission. Separate global custody/resource checks from local root input/wall/game
limits; capture under Observe's own original finite deadline capped by mission/
ending reserve, then check actual global limits again. Persist `macro_closure`
naming old root/checkpoint, fresh source, detection time and specific local limit
before clearing only the private prompt. It is not `PhaseReceipt.stage=complete`,
menu/task success, a rewritten old result or a new allowance. The player may then
explicitly choose a direct new_root from that fresh owned menu under actual
session/adoption and all original mission costs/limits. Stale old-source/queued
children receive known refusal while healthy custody survives. Exclude lifecycle,
exit, registered activity/recovery and unsettled delivery. Do not implement this
by catching generic BudgetError: global exhaustion, clock and trace faults still
stop. No additional root-replacement field or new MCP tool is selected.

Fresh campaign006 exposed a missing entry to that loop: a player tried a prompt
child after spending its root's single input. Controller preflight treated the
local accounting refusal as lost custody, so Observe could no longer close the
root. Refuse an already exhausted prompt child before controller rotation/input
preflight, retaining its immutable zero-input result and the original prompt.
Verify actual custody, source integrity and global capacity before returning that
local refusal. Explicit Observe still owns closure and the player still chooses
any new root. This uses the existing ledger, result and observation mechanisms;
there is no menu handler, automatic Escape, renewed root or generic budget-error
suppression. The [failed campaign report](../acceptance/2026-10-22-independent-seven-day-sixth-attempt.md)
separates the demonstrated failure from later source and native qualification.

Local wall expiry can also race with preparation or atomic publication. Reuse
the controller's positive known-unpublished refusal, with a trusted read-only
runtime classifier for local request/root allowance only. Keep the existing final
fatal fences and ordinary-input receipt shape; never infer local refusal by
matching an error string or forgive a published request. Preserve prepared charges
and remove only an allocated unpublished admission, treating cleanup failure as
fatal. Existing authenticated rotation/`awaiting_observation` then leads to
explicit Observe. The classifier is an internal Python callback, not a new player
tool, wire version, execution ingress or stored authority. It performs no native
input, recovery or memory curation. Passive terminal verification precedes refusal
of another input, so reaching an expected focus on the final allowed input retains
its actual result. These changes need their separate native qualification.

**Game integration and finite costs.** Owned process/session, inputs, wall time,
trace capacity and Pause are shared requirements. Character/save/turn/neighbor
proofs are integration/campaign requirements, not universal keyboard semantics.
CDDA's current campaign still requires its registered identity and actual game
clock; a game without a reliable visible clock must use an explicit unmeasured
clock policy with finite input/wall bounds, never substitute zero or claim elapsed
game time. Test the passive ordinary seam with an independently shaped fixture
without CDDA menu/neighbor/save assumptions. Full runtime extraction, setup/ending
cancellation and a real second integration remain explicit #191 work; this slice
does not claim those qualifications or replace authentic CDDA lifecycle proofs.

**Migration and retained evidence.** Native7/mission11/ledger12/archive6 form the
coordinated replacement. Update producers, validators, reservation/receipt
readers, recovery/procedure provenance, SDK/catalogue, fixtures and current
guidance together; reject superseded formats and remove the old direct branch.
The nested records are procedure/3, campaign-memory/6 and reflection/2, with
admission update policy `facts-procedures-reflection/3`. Their source schemas own
exact shapes. No compatibility reader or flag-based old path. Closed native5/
mission9 runs, original pins and accepted learning004 evidence remain immutable
historical artifacts. Do not relabel their
captured data or procedure environment. Prepare a fresh finite current-contract
learning run before using its normally closed library in the fresh campaign;
old004 is not silently mounted under a changed contract. No save is deleted.

The lead owns coupled host/schema/ledger/evidence/tooling/docs integration,
the shared native build/runtime and final verification. The native bridge and
passive ordinary policy are integrated in source; the prior isolated worker
briefs do not define a pending implementation or a second execution path.
Qualification still covers unfamiliar and time-changing receivers, preflight-only
drift, known refusals, resize/scale and masked text, negative custody/Pause/unknown ACKs,
exact immutable lineage/charges and actual independent graphical discovery. Full
campaign outcome, native click proof and causal learning/latency claims retain
their separate evidence lanes. Keep all affected artifacts aligned through057's
existing impact map and existing issue owners.

## Prefer visible targets over coordinates

Select the highest useful supported abstraction: gameplay skill, visible UI
target/action, then raw key/text/coordinate input where needed. This is a default
preference, not a ban on player exploration. The player should ask to activate a
visible control; software can resolve an ordinary hotkey, navigation/confirmation
or click without asking the model to calculate every pixel or motion/down/up.

There is already a partial foundation. The [native exporter](../../native/cdda_harness.cpp)
publishes at most32 rendered rows with presentation-local ID, text, enabled state,
displayed hotkey when available and selection. [MenuSkill](../../harness/gameplay/interaction.py)
can target a unique enabled displayed label through bounded registered navigation
and confirmation. The [item policy](../../harness/gameplay/interactions.py) and
[interpreted controls](../../harness/gameplay/semantic_controls.py) cover additional
limited selections/editors. These shortcuts require no new hit boxes. They do not
provide a general widget tree: row rectangles/roles are absent, filter/count
attestation is incomplete, and IDs are not stable item identities.

For uncovered clickable controls, investigate source-bound visible target handles
using the existing rendered-UI exporter. A future handle would resolve one visible,
enabled, unoccluded control and its applicable action or hit point in the current
presentation. Duplicate labels need an observed distinguishing context; clipping,
overlays, stale/reordered lists and unknown actionability must not select a hidden
or different item. Keep the declared root and finite limits during resolution.
Discovery of an offscreen control must use ordinary observed scrolling/navigation,
not enumeration of hidden inventory or widget internals as player knowledge.

The browser analogy is [Playwright's locators](https://playwright.dev/docs/locators)
and [actionability checks](https://playwright.dev/docs/actionability): identify a
control by user-facing attributes and check it before acting. CDDA's SDL/ImGui and
curses-style views do not have a browser DOM, so Playwright cannot directly operate
them. Reuse the principle and our current adapters before building another locator
language. Bounded waiting may retry preconditions; uncertain game input is never
retried. A request cannot silently retarget a changed scene or new list entry.

Reuse candidate: [Dear ImGui Test Engine](https://github.com/ocornut/imgui_test_engine)
provides named item operations and input injection; its
[implementation](https://github.com/ocornut/imgui_test_engine/blob/main/imgui_test_engine/imgui_te_context.cpp)
also performs automatic navigation/scrolling and some internal UI adjustments.
Evaluate a version compatible with pinned ImGui1.91.5, its
[own license](https://github.com/ocornut/imgui_test_engine/blob/main/imgui_test_engine/LICENSE.txt),
visible-only exposure and per-input accounting before adoption. It is not currently
installed and does not cover CDDA's entire mixed UI. Its autonomous action sequences
cannot become a second writer or bypass freshness, budgets, Pause or unknown
delivery handling. A thin exporter/resolver is justified only for concrete gaps
the existing adapters or a suitably bounded library do not cover; lead owns that
integration and revisits reuse if coverage grows. No dependency is selected yet.

Raw input remains available for novel screens, keyboard-only actions and spatial
game interactions without a suitable visible control. Retain the chosen target,
resolution basis and actual input/result evidence automatically. Procedure memory
should retain meaningful goals and scoped control descriptions, then resolve them
from current evidence; it must not replay old row IDs or coordinates in a new
context. Target activation is delivery, not acquisition or other game success.

## Selected boundary

The existing `enactive_skill` supports `skill_kind=direct`. The player selects
intent, desired outcome, finite limits and the exact informing source. Software
constructs the request and retains input/after-evidence through the current
composer, mission runtime, controller, ledger and official MCP adapter. No second
executor, arbitrary host commands, private JSON workflow or input transport.

| Interaction | Meaning and limit |
| --- | --- |
| Key | One printable ASCII or named key with explicit CTRL/ALT/SHIFT modifiers; one logical press/release, no held state. Preserve upstream character/keycode semantics; unsupported combinations are known refusals before input. |
| Text | At most24 printable BMP Unicode scalars in an owned ordinary menu. Expand to individually charged native scalars with fresh feedback; stop on changed structure, no visible progress, authority/budget loss or unknown delivery. No implicit Enter or blind macro. |
| Click | One left/right click at a pixel in the exact retained PNG. Validate current capture geometry and point, feed engine/widget input in process and release the button. No Mac pointer movement, focus change, drag or persistent held button. |

Every direct input requires a fresh actual dispatch capture and an attested
ordinary receiver under the same live custody. Keys/scalars permit physical-event
drift; clicks additionally retain the informing PNG's geometry. Native direct
requests require `require_exact_frame=false`; semantic operations keep their
stronger exact-frame preconditions. A returned input requires outcome verification;
an unfamiliar semantic effect does not by itself stop the mission. Unknown
delivery still requires reconciliation without replay. Real authority/storage/
budget faults retain their existing failure handling.

## Ownership and continuation

Direct roots require the mission's already-adopted character and current normal
scene, or an explicit new root from a fresh owned menu after recorded ordinary
macro closure. Direct children may continue an owned ordinary interact/item/
inspect/activity/direct prompt. They inherit its original root, Work, costs and
ceilings; changing control style cannot renew the phase. Record deviation from the original
semantic goal and do not claim that goal succeeded merely because direct input
returned. A direct quantity-editor entry cannot invent typed-count proof.

Generic ordinary in-game input contexts can be menu boundaries without a new
semantic parser per screen. Normal-play attestation remains anchored to the actual
normal scope; activity, owned interrupt and debug classifications take precedence.
Direct input cannot borrow lifecycle creation/load/save/exit authority, adopt
identity or manufacture normal-save proof. Lifecycle remains registered.

When direct input starts an activity, reuse RegisteredActivity polling,
interruption, exact-owner answering and separate Resume under the same root.
Declare interruption consent on that root. A child cannot enlarge original
consent; semantic roots without it resolve to false. No raw input at an activity,
interrupt or debug boundary. Direct phase receipts name operation `direct`,
without inventing wait/rest/craft semantics. Reopening evidence restores no lease
or live phase handles.

## Native mouse and keyboard decisions

The first source review found a viewport allocation/full-render-target mismatch.
The implemented capture uses the complete default output target and matching buffer;
retain window/output dimensions with the frame and reject changed, minimized or
invalid geometry before input. Map PNG pixels separately to engine window-local
coordinates and the pinned ImGui backend's renderer-output coordinates. Its unit
motion scale makes a shared mapping invalid on non-unit window/output ratios.
Preserve injected coordinates through the engine's physical-pointer overwrite.

`ENABLE_MOUSE=false` also sets ImGui `NoMouse`; bypassing the SDL mouse-enabled
check alone cannot make widgets clickable. Use stable harness-local synthetic
pointer handling: permit ImGui mouse consumption, suppress physical motion/button/
wheel dispatch and backend pointer polling/capture/warp while the bridge is
enabled. Deliberate physical down/wheel still triggers takeover/Pause before
filtering. Preserve keyboard takeover and browser Pause. Do not briefly toggle
`NoMouse` around queued events; consumption may happen in later frames. Non-harness
behavior retains upstream defaults. Pin the additionally patched backend file
using the existing source manifest and count-checked patcher.

Reuse upstream input events, SDL names/UTF8 and widget handling. The upstream
keychar helper mutates arrow-combo state and can read held physical keys, so it
cannot be a supposedly pure preflight. Construct/validate without effects before
the final gate. Explicit SHIFT on an unshifted printable key and its implied
glyph must agree between engine and widget paths; CTRL letters retain upstream
control-character semantics. Qualify supported modified/named keys and Unicode
entry explicitly. A rejected translation must leave delivery and game state
untouched; do not claim complete keyboard emulation from a schema alone.

## Delivery and evidence

The current coordinated contracts are recorded in the
[protocol](../protocol.md#ordinary-discovery-and-procedure-data); the
[procedure boundary](procedure-learning.md) explains the advisory integration.
The first October21 checkpoint used native5/mission9/ledger11/archive4 and
campaign-memory/4; those versions describe historical artifacts, not supported
runtime inputs. Preserve their exact captured data and pins without importing
authority or relabeling them as current-contract learning evidence.
[Delivery057](../changes/057-discovery-learning-campaign.md) retains failed runs and
source/build/install receipts. Capture001 above owns the later rebuilt boundary's
ordinary-input and normal-lifecycle qualification, retaining its unexercised drift
and commit-race branches. Actual host catalogue/preapproval activation and graphical
acceptance remain separate qualifications. Learning006 and Native001 retain their
earlier scoped evidence; none qualifies every subsequent source change.

Lead owns coupled Python integration, tests, documentation, shared build/runtime
and final verification. The isolated native implementation has been integrated;
its syntax/apply checks remain source evidence. A matching build proves
compilation, while gameplay requires separate qualification. Existing controller/
schema/ledger tooling owns dispatch and accounting; the reuse probe determines the
remaining widget-targeting gap. No separate input executor,
event bus or history system is justified.

Focused regressions cover strict events/Unicode/modifiers/coordinates, exact
source binding, root/Work/budget continuity across control styles, conservative
text batching, quantity-editor honesty, activity consent/recovery, Pause/takeover,
unknown delivery and corrupt/reopened ledgers. Native qualification separately
checks windowed/background launch, engine/widget coordinate targets including
non-unit scaling, key/text/click effects and release, stale/out-of-bounds refusal,
physical hover/takeover and owned cleanup. Preserve failures and unverified host
telemetry; mocks cannot satisfy these checks.

Prioritize qualification of the selected target/action paths and use coordinate
fallback when it is actually needed; generic mouse completeness is not a blanket
new gate for an otherwise supported #144 mission. Full #176 completion still
requires its declared click capability and evidence, or an explicit scoped product
decision; a key-only implementation is not relabeled complete mouse support.

A new finite player-owned development mission exercises actual discovery
and all original #144 supplies, shelter/rest, memory correction, fresh-context
handoff and normal same-character save/reload/final ending. Source changes happen
only after quiescence and runtime closure. No old failed admission resumes.
Native click success is not procedural learning; one complete mission does not
prove learning efficacy or complete the independent seven-day outcome.

## Native event translation and capture

The October21 isolated native5 brief was the first implementation checkpoint.
Its exact-frame direct-input requirement is superseded by native6's physical-event
drift policy above. Current [native source](../../native/cdda_harness.cpp),
[input schemas](../../harness/gameplay/native_input.py) and
[protocol](../protocol.md#transport-and-state) own the executable contract; no
historical worker brief activates a runtime or establishes graphical qualification.

All native requests/responses/control envelopes require protocol7 and reject older
versions. Existing semantic `key`/`action` and registered lifecycle/control requests
keep their stronger eligibility policies. Ordinary `kind="direct"` uses one
`input` payload on the same channel. Actual fresh dispatch source, authority,
created/deadline, boundary, revision, receiver and capture checks remain mandatory;
direct requires `require_exact_frame=false`, while clicks also require unchanged
mapping. No ordinary input at activity, interrupt, debug or unsupported boundaries.
The mission layer restricts lifecycle/identity ownership; native cannot infer a
higher-level mission from event text.

The current closed input shapes are summarized here; the schema owns exact fields:

- Key: `type="key"`, `key`, `modifiers`. Key is one printable ASCII or the
  existing supported named key; modifiers is a unique list of CTRL/ALT/SHIFT,
  maximum3. Construct/validate without reading held physical keys or mutating
  upstream arrow-combo state. Resolve explicit SHIFT consistently for engine
  glyph and widget text; CTRL letters retain upstream control semantics, with no
  accidental text injection for control shortcuts. Reject unsupported combinations
  before dispatch. Each accepted logical key has matched widget down/up.
- Text: `type="text"`, `text`, where text is exactly one printable valid Unicode
  scalar, no controls/surrogates/newline. This is one charged native primitive;
  the mission adapter expands its at-most24-scalar operation with fresh per-scalar
  feedback and no implicit Enter. Named keys are never disguised as text.
- Click: `type="click"`, `button="left"|"right"`, integer `x`/`y` in the
  exact full-output PNG and `geometry` equal to its retained frame geometry.
  One logical click returns exactly `LeftButtonReleased` or `RightButtonReleased`
  to the engine (the pinned MOUSE_LEFT/MOUSE_RIGHT selection mapping), alongside
  matched ImGui motion/down/up at the separately mapped positions. Pressed engine
  events start different drag behavior and are not this operation. No held button, pointer warp, OS focus,
  drag, wheel or extra implicit navigation.

Host validation uses one scalar and Python's `str.isprintable()`, limited to the
pinned widget build's16-bit Unicode range. Supplementary scalars refuse before
input rather than becoming a replacement glyph. Native validation
independently rejects invalid/overlong UTF-8, surrogates/out-of-range scalars,
C0/C1 controls and U2028/U2029 using the pinned decoder; it does not invent Unicode
category tables. Zero-width printable combining marks are not rejected merely for
width0. A pinned negative-width refusal is explicit unsupported input. Modified
named arrows may refuse in keychar mode before commit rather than emulate
diagonal/held-key policy; supported combinations must not read or mutate physical
key state during preflight. Full Unicode/category/shortcut parity is not claimed.

Every protocol7 observation requires `frame_geometry`, null when its frame is not
attested; otherwise an object with positive `window_width`, `window_height`,
`output_width`, `output_height` (each at most16384) and `viewport` as four integers
`[x,y,width,height]` wholly inside that output. Capture the full default render
target at output dimensions, with at most16777216 pixels before allocating the
surface; its PNG origin is output `[0,0]`. Record geometry
alongside the cached presented surface, not from a later unrelated render target.
Invalid/minimized/default-target or capture failure cannot attest a click frame.
At final click commit compare retained/request geometry with current window/output/
viewport geometry; reject changed size/scale/viewport. Physical clicks do not
require equal PNG bytes, and never retarget an old label to a new coordinate.
Non-unit geometry is a required native qualification, not established by arithmetic tests.

Map PNG pixel `(x,y)` to engine window-local
`(floor(x*window_width/output_width),floor(y*window_height/output_height))`.
The pinned widget backend uses output-pixel coordinates with its unit motion
scale; supply `(x,y)` there separately. Preserve the engine event's injected
coordinates through the physical mouse-position overwrite at input-return.
Validate point bounds and all transformations without input effects before the
existing final commit gate. Unsupported geometry is refusal, not clamping.

Harness-only pointer handling stays enabled consistently across queued widget
events. Filter physical motion/button/wheel from the ordinary engine/widget input
paths, but run deliberate physical button-down/wheel takeover BEFORE filtering.
Keyboard takeover remains unchanged. Suppress backend physical pointer polling,
capture/warp/cursor changes while the harness is enabled; non-harness behavior
remains upstream. Pin the modified backend checksum and use count-checked anchors,
including fixtures for repeatable patch application. No transient NoMouse toggle
or global mouse option change is sufficient.

Source tests cover exact fields/version, pure unsupported translation, capture
dimensions/geometry and separate coordinate transforms, injected-coordinate
preservation, stable pointer backend handling, physical takeover order and
unchanged non-harness paths. Any further native API change requires coordinated
source/schema/caller migration under the existing engineering standards.

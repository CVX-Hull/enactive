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

The selected next boundary is an ordinary-input foundation through the existing
writer, with optional semantic preconditions above it. The current source first
separates explicit Observe/redecision from automatic input refresh: a changed
healthy owned prompt can return new evidence under the same original root and
costs, clearing stale quantity proof. Automatic input still requires the exact
preflight described below. The
[delivery impact map](../changes/057-discovery-learning-campaign.md#ordinary-input-foundation-and-artifact-impact)
and #191 identify remaining native receiver, delivery/meaning, provenance and
game-integration coupling. The native5 requirements below describe the present
implementation; they are not a claim that the broader foundation is delivered.

The [organic-discovery crosswalk](organic-discovery.md#cross-check-against-prior-work)
retains prior mixed-control research, campaign findings and memory distinctions.
Independent013's unbound consume action demonstrates a catalogue/binding trap;
it does not demonstrate mouse support or general learning. Player-learned
procedures (#177) and background reflection (#178) remain separate work.

## Selected ordinary-input migration for review

This is the next #191 implementation boundary, not current runtime behavior.
Current source remains native5/mission9/ledger11/archive4 until the coordinated
candidate below is implemented, reviewed and built. The lead selected these
decisions from the actual002 failure and independent controller/receiver reviews;
the existing research crosswalk remains the evidence basis and its limits.

**Physical-event drift policy.** A direct request means the explicitly selected
key, scalar or coordinate, not an inferred semantic target. It may reach a changed
ordinary screen under the same owned session and uninterrupted actor/Pause/custody.
Retain immutable model-informing sources, entry observation, actual final preflight
and terminal evidence separately. Do not call changed evidence equivalent or change
the physical event to follow an old label. Clicks keep their original geometry;
changed mapping returns a known refusal and fresh evidence for another decision.
Keys/scalars do not require identical pixels or click geometry. Optional semantic
shortcuts retain their appropriate exact-image/native-state preconditions.

**Receiver attestation.** Native6 adds mandatory boolean
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

**Native contract.** All ordinary/control requests and observations use native6;
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

**Migration and retained evidence.** Native6/mission10/ledger12/archive5 form the
coordinated replacement. Update producers, validators, reservation/receipt
readers, recovery/procedure provenance, SDK/catalogue, fixtures and current
guidance together; reject superseded formats and remove the old direct branch.
Choose any necessary nested procedure/memory record version changes from the
actual changed schema, not a blanket version bump. No compatibility reader or
flag-based old path. Closed native5/mission9 runs, original pins and accepted
learning004 evidence remain immutable historical artifacts. Do not relabel their
captured data or procedure environment. Prepare a fresh finite current-contract
learning run before using its normally closed library in the fresh campaign;
old004 is not silently mounted under a changed contract. No save is deleted.

The lead owns coupled host/schema/ledger/evidence/tooling/docs integration and
the shared native build/runtime. After this boundary passes independent review,
one separate-worktree worker owns native bridge/header, pinned patcher/source
manifest and focused native-source tests only. A second bounded worker may own
the passive ordinary policy and its isolated tests after its exact Python API
is frozen; neither worker changes shared runtime/source outside its ownership.
Qualification covers unfamiliar and time-changing receivers, preflight-only drift,
known refusals, resize/scale and masked text, negative custody/Pause/unknown ACKs,
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

Extend the existing `enactive_skill` with `skill_kind=direct`. The player selects
intent, desired outcome, finite limits and the exact informing source. Software
constructs the request and retains input/after-evidence through the current
composer, mission runtime, controller, ledger and official MCP adapter. No second
executor, arbitrary host commands, private JSON workflow or input transport.

| Interaction | Meaning and limit |
| --- | --- |
| Key | One printable ASCII or named key with explicit CTRL/ALT/SHIFT modifiers; one logical press/release, no held state. Preserve upstream character/keycode semantics; unsupported combinations are known refusals before input. |
| Text | At most24 printable Unicode scalars in an owned ordinary menu. Expand to individually charged native scalars with fresh feedback; stop on changed structure, no visible progress, authority/budget loss or unknown delivery. No implicit Enter or blind macro. |
| Click | One left/right click at a pixel in the exact retained PNG. Validate current capture geometry and point, feed engine/widget input in process and release the button. No Mac pointer movement, focus change, drag or persistent held button. |

Every direct input requires exact-image preflight even without a semantic menu
interpretation. A returned input is partial work requiring outcome verification;
an unfamiliar semantic effect does not by itself stop the mission. Unknown
delivery still requires reconciliation without replay. Real authority/storage/
budget faults retain their existing failure handling.

## Ownership and continuation

Direct roots require the mission's already-adopted character and current normal
scene. Direct children may continue an owned ordinary interact/item/inspect/
activity/direct prompt. They inherit its original root, Work, costs and ceilings;
changing control style cannot renew the phase. Record deviation from the original
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

Source review found that capture allocates for the viewport but requests the full
render target. Capture the complete default output target into a matching buffer;
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

The implemented coordinated migration is native5, mission/9, ledger11 and evidence
archive4, with campaign-memory/4 for the selected procedure/reflection integration
and gameplay/2 record shapes unchanged. The [procedure boundary](procedure-learning.md)
and [delivery057](../changes/057-discovery-learning-campaign.md) own that combined
selection; no procedure support follows from native input alone. The historical
starting point was mission/8 and ledger10; these are no longer current contracts.
The source migrated producers, callers, strict validators, correlation/reopen
rules, fixtures and guidance together and rejects prior runtime contracts. Preserve closed
historical evidence without importing authority. The matching native build and
actual host MCP catalogue/preapproval activation are separate gates.

Lead owns coupled Python integration, tests, documentation, shared build/runtime
and final verification. After interface review, one worker may own only native
bridge/header, upstream pin and patcher in a separate project-local worktree.
Worker syntax/apply checks are source evidence, not a build or gameplay result.
Existing controller/schema/ledger tooling owns dispatch and accounting; the reuse
probe determines the remaining widget-targeting gap. No separate input executor,
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

## Candidate native5 interface for the isolated worker

This exact native side of delivery057 passed focused interface review on
October21 and is frozen for isolated implementation. This does not activate5 or
claim native qualification. The worker owns only
`native/cdda_harness.cpp`, `native/cdda_harness.h`, `native/upstream.json`,
`tools/patch_game.py` and `tests/test_setup.py`. The lead owns all Python wire/
mission/controller/ledger/SDK/evidence migration, shared build/runtime and actual
native qualification. No worker launches or patches the shared build.

All native requests/responses/control envelopes become protocol5; protocol4
rejects. Existing semantic `key`/`action` and registered lifecycle/control shapes
retain their meaning under5. They are not a second version or compatibility path.
Add ordinary `kind="direct"` with one `input` member in place of the key/action
payload: the same11 common ordinary fields plus this one payload, no new channel.
The common exact-source/authority/created/deadline/boundary/revision/frame checks
are unchanged. Direct requests additionally require `require_exact_frame=true`;
false refuses before translation/commit. No direct input at activity, interrupt,
debug or unsupported boundaries. The mission layer restricts lifecycle/identity
ownership; native cannot infer a higher-level mission from event text.

The closed input shapes are:

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

Every protocol5 observation adds `frame_geometry`, null when its frame is not
attested; otherwise an object with positive `window_width`, `window_height`,
`output_width`, `output_height` (each at most16384) and `viewport` as four integers
`[x,y,width,height]` wholly inside that output. Capture the full default render
target at output dimensions, with at most16777216 pixels before allocating the
surface; its PNG origin is output `[0,0]`. Record geometry
alongside the cached presented surface, not from a later unrelated render target.
Invalid/minimized/default-target or capture failure cannot attest a click frame.
At final click commit compare retained/request geometry with current window/output/
viewport geometry AND exact saved PNG; reject changed size/scale/viewport even if
the image comparison alone could look identical. Non-unit geometry is a required
native qualification, not established by arithmetic tests.

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
unchanged non-harness paths. Any additional concrete native API needed must be
reported to the lead before changing this interface or worker ownership.

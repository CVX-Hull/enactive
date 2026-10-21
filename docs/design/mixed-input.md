---
owner: lead
review_trigger: Ordinary input schema, native keyboard/mouse handling, phases or evidence migration changes
status: proposed
---

# Mixed skills and ordinary interaction

The player should use skills for efficient familiar work and ordinary keys, text
or deliberate clicks for discovery. Both go through the same mission writer;
switching must preserve the original work, costs and uncertain outcomes. This
selected design for [#176](https://github.com/CVX-Hull/enactive/issues/176) is not
implemented input support. Current [architecture](../architecture.md) and
[protocol](../protocol.md) remain authoritative.

The [organic-discovery crosswalk](organic-discovery.md#cross-check-against-prior-work)
retains prior mixed-control research, campaign findings and memory distinctions.
Independent013's unbound consume action demonstrates a catalogue/binding trap;
it does not demonstrate mouse support or general learning. Player-learned
procedures (#177) and background reflection (#178) remain separate work.

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

The proposed coordinated migration is native5, mission/8, ledger10 and evidence
archive4, with campaign-memory/3 and gameplay/2 record shapes unchanged. Migrate
all current producers, callers, strict validators, correlation/reopen rules,
fixtures and guidance together; reject prior runtime contracts. Preserve closed
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

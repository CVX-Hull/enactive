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
The existing upstream/controller/schema/ledger tooling covers the requirement;
no new input framework, event bus or history system is justified.

Focused regressions cover strict events/Unicode/modifiers/coordinates, exact
source binding, root/Work/budget continuity across control styles, conservative
text batching, quantity-editor honesty, activity consent/recovery, Pause/takeover,
unknown delivery and corrupt/reopened ledgers. Native qualification separately
checks windowed/background launch, engine/widget coordinate targets including
non-unit scaling, key/text/click effects and release, stale/out-of-bounds refusal,
physical hover/takeover and owned cleanup. Preserve failures and unverified host
telemetry; mocks cannot satisfy these checks.

Then a new finite player-owned development mission exercises actual discovery
and all original #144 supplies, shelter/rest, memory correction, fresh-context
handoff and normal same-character save/reload/final ending. Source changes happen
only after quiescence and runtime closure. No old failed admission resumes.
Native click success is not procedural learning; one complete mission does not
prove learning efficacy or complete the independent seven-day outcome.

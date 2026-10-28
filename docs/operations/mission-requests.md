---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Typed mission requests and the player

Deciding players start with the [compact working guide](../player-guide.md), their
frozen brief and the selected current tool schema. This runbook is a focused
reference; reading all engineering documents or recursively searching runtime
artifacts during play is not required to use the interface.

The current service has one mission runtime and `/api/mission`. The old waypoint
Start/Continue/Abandon/planner inbox and `gameplay-*` CLI are removed, with no alias.
The [mission contract](../contracts/mission-admission.md#integrated-mission-lifecycle) and strict source
schema own the supported records; the [design](../design/player-owned-mission.md)
separates implemented components from remaining independent-play acceptance.

1. Declare development or formal-acceptance purpose under
   [development-first delivery](../workflows/development.md#development-first-delivery).
   Development uses fast/focused checks; formal acceptance of its result needs
   review and successful exact-candidate CI under the
   [profile policy](../workflows/ci-profiles.md#protected-ci-profiles), including full
   regression for broad source changes; this may follow the unchanged run.
   Before admission, query GitHub for the selected candidate's current required
   check status and retain the lookup time; use the existing CLI/API rather than
   hand-copying a previous poll as a freeze-time fact. Pending development checks
   remain explicit; adjudicate an applicable failed check before affected input.
   This is setup work, not a player task or a per-action CI/approval round trip.
   Freeze the exact source commit,
   finite objective/scenario/limits/reserve,
   actor, native build and permission preflight before gameplay. The initial
   admission is not authority to adopt an unrelated open character.
   Validate proposed fresh world/character names against the actual edit-goal
   JSON Schema through the existing validator: current whole-value editing accepts
   at most24 supported ASCII characters, while Scenario can describe80-character
   load identities. Budget TEXT.CLEAR plus typing and a separately interpreted
   commit. A lifecycle root includes Resume and ALL child inputs cumulatively;
   larger child limits do not extend it. Freeze a sufficient whole-phase budget
   prospectively, leaving the mission cleanup reserve intact. This pure feasibility check is not native acceptance; recheck when
   editor/schema/scenario changes. Never shorten an immutable admitted identity.
2. Configure and verify the [structured player tools](../setup.md#configure-the-structured-player-tools).
   The designated player uses `enactive_snapshot` and explicitly selects the
   returned snapshot/source IDs for `enactive_skill` or `enactive_lifecycle`.
   Software constructs and retains the current mission/11 request before submission,
   collects its bounded result and returns the actual retained PNG in the same call.
   MCP software assigns request IDs and result waits; old caller-owned
   `request_id`/`wait_seconds` arguments are rejected. Execution limits remain
   explicit. An assigned-ID error carries `original_collection` so uncertain
   dispatch can collect its actual operation; a new invocation is never a retry.
   The lead uses `enactive_start` for the explicit frozen source-free admission;
   it does not launch or adopt a character. Raw engineering contract diagnostics
   retain the validated `mission-request` CLI. They are not a second player or a
   per-action file-writing recipe.
3. Start is source-free; explicit Observe is passive. Registered owned lifecycle must establish
   world/character identity and fresh input authority. Source lifecycle composition
   has source coverage, scoped Native007 qualification and actual
   [independent024 mission evidence](../acceptance/2026-10-21-independent-supply-shelter.md).
   A new mission must meet its own original outcomes; historical success grants no authority.
   Do not substitute raw keys/Resume or a trusted unit fixture.
4. Read the result by its exact operation ID. Accepted only acknowledges admission;
   wait for the settled immutable result and inspect the frame/effect. A lost response
   is not nondelivery. Never change a request body under an existing ID or blindly
   replay an uncertain input. Busy admission is a visible rejection, not a queued
   future action.
   The structured tool returns pending/uncertain delivery explicitly; use
   `enactive_result` with the original ID. Do not generate another ID to retry.
   Identical previously staged requests collect only; a changed body under that
   identity refuses. Descriptive handles expire with the adapter or bounded cache;
   explicitly read a new snapshot/source instead of reconstructing authority.
   Known returned/rejected ACKs retain delivery even if capture storage or later
   processing fails. Inspect separate evidence-loss/processing diagnostics. A
   publication bookkeeping diagnostic alone permits continuation when mandatory
   atomic settlement succeeds and custody/evidence remain healthy. The
   ACK's historical after-source is separate from actual current evidence; a
   different current source ends the operation partial for another player decision.
   A healthy newer native view does not erase the actual captured source or ACK.
   Semantic non-equivalence sends no input; inspect the returned fresh evidence.
   If the result requests Observe, make that explicit observation before choosing
   a distinct input. Old text batches never resume. Actual custody, clock/revision,
   source-integrity and unresolved-delivery failures retain their stopping path.
5. The player requests bounded context, reads needed retained sources, records
   fallible claims/corrections/Work and chooses semantic goals. The observer's last
   context packet is historical, query-specific and possibly incomplete. Its labels
   are as-of that packet; use a new explicit query to judge current knowledge.
   Use `enactive_context`, `enactive_remember` and `enactive_correct`; memory content
   and truthful support/read declarations remain the player's responsibility.
   Handoff, claim and separately charged readmission are explicit tools. A client
   process replacement is not evidence that a fresh model context read the memory.
6. Use `skill_kind=direct` for an explicitly chosen physical key, scalar/text batch
   or click at a live ordinary receiver. Keys/scalars permit changed pixels under
   the same custody; clicks retain the selected image's geometry. Inspect returned
   evidence and choose again after a partial result. Semantic shortcuts retain
   their strict source/control requirements. Owned menus support bounded focusing,
   literal text and direction/confirmation
   handling. Dismissal uses its exact registered context action (TEXT.QUIT,
   UILIST.QUIT, WORLDGEN_CONFIRM.QUIT or ordinary QUIT). A rowless any-key
   POPUP_WAIT supports one SPACE acknowledgement under the exact signature in
   [the protocol](../protocol.md); other controls are never guessed. Dismissal returns
   partial for effect
   verification and never automatically answers a new prompt. Original
   root/child limits and unknowns stay recorded. Untouched-menu exit uses its owned
   lifecycle root and an explicit interpreted confirmation child. It is not a
   character save/exit path. Item/activity, creation/save/reload and handoff adapters
   compose in source. Scoped native lifecycle and actual024primary/successor
   evidence are linked above; neither promises every future interface or campaign outcome.
7. Pause prevents further admission, without undoing an input or native activity.
   Honor user Pause/takeover; do not auto-Resume or restore a phase from disk. A
   stopped deciding attempt remains stopped. Retain its original artifacts and
   concise closure/finding note; consolidate reporting at the integration checkpoint.
   Normal cleanup, actual fresh-context
   replacement and full mission acceptance are separately required.

Allocate root limits for the entire phase: normal prompt-opening roots normally
use the existing32-primitive ceiling, with room for all child selections/editing,
verification and return; lifecycle setup uses its prospective whole-phase preset.
One opening input is not the whole inspection. Limits spend only actual admitted
primitives. Child limits can narrow their root, never enlarge it. Zero-input local
budget refusals permit a new corrected request. An exhausted ordinary macro can
close only through explicit Observe as described above; other exhausted live
roots retain their existing stops.

The lead owns source/integration/admission and verification. The deciding player
owns ordinary tactics and supported lifecycle; source faults or unsupported required
capabilities stop the attempt with evidence instead of inviting engineering rescue.
Role assignment is procedural, not filesystem isolation. Optional curation or
additional model tiers do not gate this functional path. No paid API is implied.

[Operations index](../runbook.md).

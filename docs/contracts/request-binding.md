---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Skill request binding errors

MCP preserves a mutation's assigned `original_collection` on unfinished or transport-uncertain
responses, including when its immediate snapshot cannot be obtained. The identity
comes from the original composed invocation; it grants only exact collection,
not admission, delivery proof, replay, source freshness or input authority.
Proven unsubmitted/nonadmitted refusals retain their separate correction path.

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

An activity child additionally supplies the exact canonical `original_root` to
this pure producer. Player tools obtain it using the existing read-only original
result collection, selected by this phase's origin request ID, before staging the
new child. The producer validates its current request schema, same mission and
exact phase origin, root shape and permitted activity/direct/program kind. It
does not require the original root to have the child's current epoch. Missing,
unavailable or mismatched roots refuse before a new child is staged or submitted;
no new endpoint, store, replay or authority follows from collection.

A child `step=poll` additionally requires the explicitly selected source's boundary
kind to be `activity_poll`. A selected menu or other boundary produces a local
pre-staging refusal. This is an as-of consistency check, not a freshness or
authority claim: a once-valid selected source can still become stale before
dispatch, and the receiver retains its live boundary/custody checks. A returned
`awaiting_control` menu needs another deliberate decision under the published
phase and original limits; it is not an instruction to poll again. No automatic
input, refresh, phase closure or budget renewal follows. Existing staged or
unknown requests retain their original collection obligations.

## Skill goals, support and applicability refusal

Current SDK/MCP skill intents also omit navigation `goal.scope` and activity
`goal.interrupt_request_id`; supplied copies reject, even when null or correct.
Navigation copies only a published coordinate scope matching this snapshot's
mission and selected normal source session. It never substitutes mission epoch
or zero for a coordinate epoch. Activity start chooses `step=start`, operation
(wait/rest/craft), target, game_seconds and interrupt_allowed, without answer or
owner. An activity child supplies only poll/interrupt/resume, or answer_interrupt
with explicit YES/NO. Copied stable fields reject. A semantic activity root's
operation, target, duration and consent are copied exactly; an insufficient child
limit rejects rather than changing that duration. Direct/program roots instead
derive operation=direct, target from the original expected outcome and original
interrupt consent; their activity duration is the minimum of the original game
ceiling, explicit child game ceiling and activity wire maximum. This bound does
not modify either request's limits or the original cumulative accounting.
An explicit activity answer binds only an
unanswered `interrupt_confirmation` phase with the selected primary checkpoint
and the same nonnull owner in the selected native boundary. Other activity steps
generate null ownership. The caller still chooses the step/answer, outer scope,
source and finite limits. Missing/inconsistent selected metadata refuses before
submission; final canonical validation and live runtime guards remain unchanged.

Additional informing source IDs are explicit bounded support: a two-observation
transition selects its latest binding bundle and cites its first observation as
support. A phase scope requires that exact summary/checkpoint, without falling
back to another phase or null root. Prompt supports only menu/edit/inspect/item/
activity children; activity scope supports only activity. Lifecycle children keep
their direct create/save/load root, including ordinary controls and provisional identity inspection;
owned-exit controls are lifecycle-scoped ordinary or menu children. No unrelated Work attaches
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
[Deciding002](../acceptance/2026-10-20-independent-mission-second-attempt.md) retains
the stale-boundary failure that motivated this change; it cannot resume.
[Native009](../acceptance/2026-10-20-request-construction-qualification.md) separately
failed before the declared probe after omitting the direct identity root. It cannot
resume either; pure producer tests do not replace a new finite native qualification.

## Semantic menu controls and prompt limits

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
[Native010](../acceptance/2026-10-20-menu-dismissal-qualification.md) exercised the
narrow binding correction, then failed normal ending on the old generic-QUIT
mapping. [Native011](../acceptance/2026-10-20-registered-dismissal-qualified.md)
subsequently qualified actual registered UILIST dismissal and normal ending.
The failed Native010 attempt cannot resume; later qualification does not rewrite it.

[Contract index](../protocol.md).

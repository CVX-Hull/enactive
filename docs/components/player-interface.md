---
owner: harness maintainer
review_trigger: Player tools, context, SDK staging, host presentation or model responsibilities change
status: active
---

# Player interface: judgment in, bounded evidence out

Parent: [system architecture](../architecture.md). This view answers: “What must
the player decide, and what should software handle?” One designated player plans,
interprets visible evidence, chooses intent/sources/limits and judges outcomes.
The lead owns engineering and verification; routine play and curation do not wait
for the lead. The adviser proposes data without input authority.

## Internal responsibilities

| Block | Responsibility and owned state | Implementation |
| --- | --- | --- |
| MCP adapter | Official SDK framing, tool exposure, JSON text and actual image parts; no game launch/executor | [player_mcp.py](../../harness/player_mcp.py) |
| Player tools | Current semantic schemas, bounded selected snapshot/source/procedure caches, mechanical request metadata | [player_tools.py](../../harness/player_tools.py) |
| Decision projection | Small current decision view; exact retained detail available on demand | [player_view.py](../../harness/player_view.py) |
| Imperative client | Immutable staged requests, HTTP ingress and original result collection | [mission_client.py](../../harness/mission_client.py) |
| Host driver | Finite host activation and at most the admitted successor after real quiescent handoff | [campaign_player.py](../../tools/campaign_player.py) |

The flow is selected snapshot + explicit player intent → request composition →
durable SDK stage → existing mission ingress → original collection → decision
view and image. Mechanical IDs, waits, canonical metadata and joins belong to
software. It must not guess intent, choose supporting evidence, repair malformed
arguments, replay input or turn a detail read into a new observation.

For an activity child, the player chooses only the step and any explicit YES/NO
answer. Before staging, player tools collect the exact original request selected
by the published phase through the existing read-only result interface. The pure
composer inherits immutable activity semantics and binds the answer owner from
the selected checkpoint. Missing or inconsistent context refuses before a new
child is staged; this read neither refreshes authority nor extends limits.
Activity start still requires the player's operation, target, duration and
interrupt consent. The [protocol](../protocol.md#skill-request-binding-errors)
owns the distinction between semantic duration and an ordinary root's ceiling.

## Context and failure boundaries

Default responses expose the next decision, relevant visible state, active scope,
remaining original capacity, uncertainty and obligations. Exact cached details and
source images are progressively available. Source metadata fits the permitted
handoff working set; eviction requires an explicit exact reread, not authority
restoration. A cache is neither durable history nor proof of model attention.

The current `player-view/5` projects known technical fields from historical-source
references and memory packet source references, plus the context configuration's
native binary hash. It preserves source IDs, visible state, uncertainty, authored
claims/procedures and images. This is typed projection, never recursive deletion
of similarly named authored fields. Raw SDK source/context responses and retained
evidence remain complete. `enactive_detail` returns exact sections of its selected
cached snapshot; it does not turn that snapshot into a different historical source.
Historical machine bindings remain available through `MissionClient.source` and
the original context response, rather than another model-facing audit endpoint.

![Known refusal, admitted work and uncertainty have different next decisions.](../diagrams/request-receipts.svg)

The [editable view](../diagrams/request-receipts.mmd) answers when the player can
correct a request and when the original operation still needs collection.

A positively pure new preparation refusal can be `not_submitted`. Existing stages,
failed stage lookup and uncertainty from staging onward retain original collection
arguments. A transport or presentation error proves neither delivery nor
nondelivery. Restart cannot reconstruct missing settled identities or permission
to replay. The [binding contract](../protocol.md#skill-request-binding-errors)
and [operator contract](../protocol.md#designated-campaign-operator) own exact rules.

For a selected active, idle prompt with no activity/lifecycle phase, a refused new
root points to explicit Observe. Observe may close a locally exhausted ordinary
macro; the player inspects its returned phase and chooses a continuation or a new
bounded root. The composer neither performs that read nor promises closure. Whole
mission capacity is not local root capacity. Pause, pending operations and other
phases retain their distinct rules; the original root and all costs remain intact.

A narrowly certified receiver refusal is `submission=not_admitted`: the SDK has
validated an authenticated `mission-refusal/1` against its immutable staged
request. The player can select a new corrected decision; software assigns its new
identity. No nonexistent operation is collected, and the refused stage is retained
without replay. Generic refusals, malformed certificates and lost responses do
not establish this fact. Machine binding/digest fields stay out of default MCP
context; raw SDK evidence retains them. See the
[exact contract](../protocol.md#certified-request-admission-refusal).

An advisory Claim's validated `busy, admitted=false` receipt proves zero admission;
its local fence can be released for another bounded attempt. Missing receipts,
uncertainty and admitted commands remain collection-only. This exception does not
retry gameplay or advisory submissions. Image deduplication records presentation
in the response-building path, after background work returns. Failed/cancelled
responses and intervening historical-source images cannot suppress an unseen image.

The actual host's loaded schema, image presentation and context sufficiency need
qualification; SDK tests alone do not establish those properties. Routine player
work starts with the compact [guide](../player-guide.md), frozen mission and
selected tool schema, without source archaeology or the engineering corpus.

## Assurance and evidence

Review mechanical vs semantic responsibilities first, then ingress/staging failure
boundaries, then projection/cache code. These are representative risks, not a
complete test inventory. The staging and projection mechanisms below implement
[C-RUNTIME](../controls.md#c-runtime--live-authority-and-input-guards-runtime);
[C-PORTABLE](../controls.md#c-portable--portable-regression-lane-automatic) executes
their source regressions. Import contracts separately prohibit these adapters
from instantiating an executor.

| User consequence | Invariant and contract | Mechanism, representative assertion and limit |
| --- | --- | --- |
| A lost response or repeated call sends another action | Staged intent stays immutable; uncertainty requires original collection. [Binding contract](../protocol.md#skill-request-binding-errors). | MissionClient staging: [client](../../tests/test_mission_client.py) `test_duplicate_only_collects_same_operation_and_changed_payload_refuses` asserts one submission followed by result collection and rejects changed payload. [Player tools](../../tests/test_player_tools.py) `test_unknown_delivery_is_preserved_without_retry_or_implicit_input` asserts one ambiguous submission, unchanged delivered inputs and retained uncertainty. These `assurance_ingress` fixtures do not prove real host delivery. |
| Compact context erases the player's evidence or changes retained detail | Project only known binding fields, preserve authored content and isolate copies. [Context boundary](#context-and-failure-boundaries). | Decision projection: [view tests](../../tests/test_player_view.py), selected by `assurance_context`, assert authored claim/procedure preservation and no cache mutation/aliasing. Synthetic records and a controlled client do not prove sufficient context or actual image presentation. |
| A mechanically valid response still leaves the player unable to continue | The actual host must load the schema, show relevant evidence and support a useful next decision. [Operator contract](../protocol.md#designated-campaign-operator). | [C-USABILITY](../controls.md#c-usability--operator-understanding-review-manual) requires observed use and reader judgment. The retained [useful-play assessment](../acceptance/2026-10-25-useful-play-readiness.md) demonstrates bounded continuation but records failed normal ending and rejected whole-player readiness. Tags and SDK passes cannot qualify this outcome. |

The [evaluation](../evaluation.md#latency-budgets-for-interactive-play) owns useful
latency definitions; short calls or token-cache rates do not qualify play cadence.

Current limitations and actions belong to [#164](https://github.com/CVX-Hull/enactive/issues/164)
and the linked campaign issues. A host report describes observed host events, not
current process liveness, fresh memory use, normal game cleanup or successful play.

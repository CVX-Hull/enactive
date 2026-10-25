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

![Known refusal, admitted work and uncertainty have different next decisions.](../diagrams/request-receipts.svg)

The [editable view](../diagrams/request-receipts.mmd) answers when the player can
correct a request and when the original operation still needs collection.

A positively pure new preparation refusal can be `not_submitted`. Existing stages,
failed stage lookup and uncertainty from staging onward retain original collection
arguments. A transport or presentation error proves neither delivery nor
nondelivery. Restart cannot reconstruct missing settled identities or permission
to replay. The [binding contract](../protocol.md#skill-request-binding-errors)
and [operator contract](../protocol.md#designated-campaign-operator) own exact rules.

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

## Review and evidence

Review mechanical vs semantic responsibilities first, then ingress/staging failure
boundaries, then projection/cache code. Focused tool/client/view/MCP tests live in
[tests](../../tests/); import contracts prohibit these adapters from instantiating
an executor. Changed presentation also needs actual host usability evidence before
claiming independent continuation. The [evaluation](../evaluation.md) owns useful
latency definitions; short calls or token-cache rates do not qualify play cadence.

Current limitations and actions belong to [#164](https://github.com/CVX-Hull/enactive/issues/164)
and the linked campaign issues. A host report describes observed host events, not
current process liveness, fresh memory use, normal game cleanup or successful play.
